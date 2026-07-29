from rest_framework.decorators import api_view
from rest_framework.response import Response


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
