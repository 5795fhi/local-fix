from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from accounts.models import ProviderProfile
from .models import ServiceCategory

User = get_user_model()


def category_list(request):
    categories = ServiceCategory.objects.filter(is_active=True)
    return render(request, "services/category_list.html", {"categories": categories})


def provider_directory(request):
    """Browse and search approved, available providers."""
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()

    providers = (
        ProviderProfile.objects.filter(is_approved=True)
        .select_related("user")
        .prefetch_related("categories")
    )
    if category_slug:
        providers = providers.filter(categories__slug=category_slug)
    if query:
        providers = providers.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(headline__icontains=query)
            | Q(service_area__icontains=query)
            | Q(categories__name__icontains=query)
        ).distinct()

    context = {
        "providers": providers.order_by("-rating_avg", "-rating_count"),
        "categories": ServiceCategory.objects.filter(is_active=True),
        "query": query,
        "active_category": category_slug,
    }
    return render(request, "services/provider_directory.html", context)


def provider_detail(request, pk):
    profile = get_object_or_404(
        ProviderProfile.objects.select_related("user").prefetch_related("categories"),
        pk=pk,
        is_approved=True,
    )
    reviews = profile.user.reviews_received.select_related("customer").order_by(
        "-created_at"
    )[:10]
    return render(
        request,
        "services/provider_detail.html",
        {"profile": profile, "reviews": reviews},
    )
