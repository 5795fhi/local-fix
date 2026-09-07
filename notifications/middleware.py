class NotificationCountMiddleware:
    """Attach the unread notification count to every authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.unread_notifications = 0
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            request.unread_notifications = user.notifications.filter(
                is_read=False
            ).count()
        return self.get_response(request)
