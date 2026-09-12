from django.urls import path

from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.chat, name="chat"),
    path("c/<int:conversation_id>/", views.chat, name="chat_detail"),
    path("send/", views.send_message, name="send"),
    path("book/", views.book_from_chat, name="book"),
    path("new/", views.new_conversation, name="new"),
    path("c/<int:conversation_id>/delete/", views.delete_conversation, name="delete_conversation"),
]
