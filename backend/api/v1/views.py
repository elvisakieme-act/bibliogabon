from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(
    tags=["API"],
    summary="Retrieve API version information",
    responses=inline_serializer(
        name="ApiIndex",
        fields={
            "name": serializers.CharField(),
            "version": serializers.CharField(),
            "docs": serializers.CharField(),
            "schema": serializers.CharField(),
        },
    ),
)
@api_view(["GET"])
def api_index(request):
    return Response(
        {
            "name": "BiblioGABON API",
            "version": "v1",
            "docs": "/api/docs/",
            "schema": "/api/v1/schema/",
        }
    )
