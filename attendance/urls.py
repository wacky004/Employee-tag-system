from django.urls import path

from .views import CorrectionRequestCreateView, CorrectionReviewListView

app_name = "attendance"

urlpatterns = [
    path("corrections/", CorrectionRequestCreateView.as_view(), name="corrections"),
    path("corrections/review/", CorrectionReviewListView.as_view(), name="correction-review"),
]
