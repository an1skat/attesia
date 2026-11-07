from django.urls import path

from app.modules.credentials.api.v1.views import (
    CredentialDetailView,
    CredentialRevokeView,
    EventCredentialListCreateView,
)

app_name = "credentials"
urlpatterns = [
    path(
        "events/<int:event_id>/credentials/",
        EventCredentialListCreateView.as_view(),
        name="event_credential_list",
    ),
    path(
        "credentials/<uuid:public_id>/",
        CredentialDetailView.as_view(),
        name="credential_detail",
    ),
    path(
        "credentials/<uuid:public_id>/revoke/",
        CredentialRevokeView.as_view(),
        name="credential_revoke",
    ),
]
