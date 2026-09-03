from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .gateway import chat_completion
from .models import Conversation, Message


@login_required
def chat(request, conversation_id=None):
    conversations = request.user.conversations.all()
    conversation = None
    if conversation_id:
        conversation = get_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )
    elif conversations.exists():
        conversation = conversations.first()

    return render(
        request,
        "assistant/chat.html",
        {"conversations": conversations, "conversation": conversation},
    )


@login_required
@require_POST
def send_message(request):
    content = (request.POST.get("message") or "").strip()
    if not content:
        return JsonResponse({"error": "Message is required."}, status=400)

    conversation_id = request.POST.get("conversation_id")
    if conversation_id:
        conversation = get_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )
    else:
        conversation = Conversation.objects.create(
            user=request.user, title=content[:60]
        )

    Message.objects.create(
        conversation=conversation, role=Message.Role.USER, content=content
    )

    history = [
        {"role": m.role, "content": m.content}
        for m in conversation.messages.all()
        if m.role in (Message.Role.USER, Message.Role.ASSISTANT)
    ]
    reply = chat_completion(history)
    assistant_msg = Message.objects.create(
        conversation=conversation, role=Message.Role.ASSISTANT, content=reply
    )
    conversation.save(update_fields=["updated_at"])

    return JsonResponse(
        {
            "conversation_id": conversation.id,
            "reply": assistant_msg.content,
            "created_at": assistant_msg.created_at.strftime("%H:%M"),
        }
    )


@login_required
@require_POST
def new_conversation(request):
    conversation = Conversation.objects.create(user=request.user)
    return redirect("assistant:chat_detail", conversation_id=conversation.id)


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(
        Conversation, pk=conversation_id, user=request.user
    )
    conversation.delete()
    return redirect("assistant:chat")
