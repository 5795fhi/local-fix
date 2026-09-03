from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required, verified_required
from accounts.models import User
from notifications.models import Notification
from .forms import ComplaintForm, ComplaintResolveForm
from .models import Complaint


@verified_required
def raise_complaint(request):
    if request.method == "POST":
        form = ComplaintForm(request.POST, user=request.user)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.raised_by = request.user
            complaint.save()
            # Alert every admin.
            for admin in User.objects.filter(role=User.Role.ADMIN):
                Notification.notify(
                    admin, "New complaint", complaint.subject,
                    url="/complaints/manage/",
                )
            messages.success(request, "Your complaint has been submitted.")
            return redirect("complaints:my_complaints")
    else:
        form = ComplaintForm(user=request.user)
    return render(request, "complaints/raise.html", {"form": form})


@verified_required
def my_complaints(request):
    complaints = request.user.complaints_raised.select_related("booking")
    return render(request, "complaints/my_complaints.html", {"complaints": complaints})


@role_required(User.Role.ADMIN)
def manage_complaints(request):
    status = request.GET.get("status")
    qs = Complaint.objects.select_related("raised_by", "booking")
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "complaints/manage.html",
        {"complaints": qs, "statuses": Complaint.Status.choices, "active_status": status},
    )


@role_required(User.Role.ADMIN)
def resolve_complaint(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)
    if request.method == "POST":
        form = ComplaintResolveForm(request.POST, instance=complaint)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.handled_by = request.user
            complaint.save()
            Notification.notify(
                complaint.raised_by,
                "Complaint update",
                f"Your complaint '{complaint.subject}' is now {complaint.get_status_display()}.",
                url="/complaints/",
            )
            messages.success(request, "Complaint updated.")
            return redirect("complaints:manage")
    else:
        form = ComplaintResolveForm(instance=complaint)
    return render(
        request, "complaints/resolve.html", {"form": form, "complaint": complaint}
    )
