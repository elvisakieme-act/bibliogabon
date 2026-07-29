from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.v1.serializers import ErrorResponseSerializer


@extend_schema(
    tags=["API"],
    summary="Retrieve API version information",
    responses={
        200: inline_serializer(
            name="ApiIndex",
            fields={
                "name": serializers.CharField(),
                "version": serializers.CharField(),
                "docs": serializers.CharField(),
                "schema": serializers.CharField(),
            },
        ),
        401: ErrorResponseSerializer,
    },
    examples=[
        OpenApiExample(
            "API version",
            value={
                "name": "BiblioGABON API",
                "version": "v1",
                "docs": "/api/docs/",
                "schema": "/api/v1/schema/",
            },
            response_only=True,
            status_codes=["200"],
        )
    ],
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
