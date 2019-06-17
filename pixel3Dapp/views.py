import os
import tempfile

from django.shortcuts import render
from django.conf import settings
from django.core.files import File

from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer

from .serializers import SpriteSerializer
from .serializers import ColorMapSerializer

from .models import Sprite
from .models.color_map import unserializeColorMap 
from .models.pixel_map import unserializePixelMap

import pixel3d.pixel3dgenerator as pixel3dGenerator

def index(request):
    return render(request, 'pixel3d/index.html', {})

class TemporaryModelFile:
    def __init__(self, sprite_id):
        self.filePath = sprite_id + "_model.stl"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if os.path.exists(self.filePath):
            os.remove(self.filePath)

class SpriteSet(viewsets.ModelViewSet):
    queryset = Sprite.objects.all()
    serializer_class = SpriteSerializer

    def create(self, request):
        # Request data should contain the sprite name and the 2D sprite file
        serializer = SpriteSerializer(data=request.data)
        if serializer.is_valid():
            # Save user provided data
            serializer.save()

            # Gets the new sprite
            newSprite = Sprite.objects.get(pk = serializer.data["id"])

            # Generates its pixel map
            input_file_path = os.path.join(settings.MEDIA_ROOT, newSprite.sprite.name)
            pixelMap = pixel3dGenerator.generatePixelMap(input_file_path)
            unserializePixelMap(pixelMap, newSprite)

            # saves the new sprite
            newSprite.save()

            # returns the new sprite
            serializer = SpriteSerializer(newSprite)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def partial_update(self, request, pk=None):
        sprite = Sprite.objects.filter(id=pk)
        if sprite.exists():
            serializer = SpriteSerializer(sprite.get(), data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_404_NOT_FOUND)


    def destroy(self, request, pk=None):

        spriteToDestroy = Sprite.objects.filter(id=pk)
        if spriteToDestroy.exists():
            filePath = os.path.join(settings.MEDIA_ROOT, spriteToDestroy.get().sprite.name)
            deleted_rows = spriteToDestroy.delete()

            if deleted_rows[0] > 0:
                if(os.path.exists(filePath)):
                    os.remove(filePath)
                return Response(status=status.HTTP_200_OK)
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @action(methods=["put"], detail=True)
    def process(self, request, pk=None):
        sprite = Sprite.objects.filter(id=pk)
        if sprite.exists():
            sprite = sprite.get()

            input_file_path = os.path.join(settings.MEDIA_ROOT, sprite.sprite.name)

            # Generate the color map, as an array
            colorMap = pixel3dGenerator.generateColorMap(input_file_path, 10)

            # Convert the array to a colorMap object
            unserializeColorMap(colorMap, sprite)
            
            # Sets the colorMap field, and save the sprite
            # sprite.colorMap = colorMap
            sprite.save()

            # Send back the serialized created sprite
            serializer = SpriteSerializer(sprite)

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_404_NOT_FOUND)

    """
    @action(methods=["get"], detail=True)
    def color_map(self, request, pk=None):
        sprite = Sprite.objects.filter(id=pk)
        if sprite.exists():
            input_file_path = os.path.join(settings.MEDIA_ROOT, sprite.get().sprite.name)
            colorMap = pixel3dGenerator.generateColorMap(input_file_path, 10)

            return Response(colorMap, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)
    """


    @action(methods=["put"], detail=True)
    def export(self, request, pk=None):
        sprite = Sprite.objects.filter(id=pk)
        if sprite.exists():

            with TemporaryModelFile(pk) as tempModelFile:
                input_file_path = os.path.join(settings.MEDIA_ROOT, sprite.get().sprite.name)
                pixel3dGenerator.exportToStl(sprite.get().heightMap, tempModelFile.filePath, 10)


                with open(tempModelFile.filePath, "r+b") as output_file:
                    serializer = SpriteSerializer(sprite.get(), data={ 'model3d': File(output_file) }, partial=True)

                    if serializer.is_valid():
                        # input_file_path = os.path.join(settings.MEDIA_ROOT, sprite.get().sprite.name)
                        # output_file_path = os.path.join(settings.MEDIA_ROOT, serializer.data["model3d"].name)
                        # pixel3dGenerator.main(input_file_path, output_file_path, 10, 30)
                        print("save")
                        serializer.save()
                        print("ok")
                        return Response(serializer.data, status=status.HTTP_200_OK)
                    print(serializer.errors)
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_404_NOT_FOUND)
