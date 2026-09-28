from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user

from extensions import db
from models import Conversation, Message, User

chat_bp = Blueprint("chat", __name__)


def _get_seller_id():
    admin = User.query.filter_by(role="admin").first()
    return admin.id if admin else None


def _authorize(conversation):
    if current_user.is_admin:
        if conversation.seller_id != current_user.id:
            abort(403)
    elif conversation.customer_id != current_user.id:
        abort(403)


@chat_bp.route("/")
@login_required
def conversations():
    """Customer's own conversation list. Admins use /admin/chats instead."""
    convos = Conversation.query.filter_by(customer_id=current_user.id) \
        .order_by(Conversation.last_message_at.desc()).all()
    for c in convos:
        c.refresh_expiration()
    active = [c for c in convos if c.status == "ACTIVE"]
    others = [c for c in convos if c.status != "ACTIVE"]
    return render_template("chat/conversations.html", active=active, others=others)


@chat_bp.route("/start-inquiry", methods=["POST"])
@login_required
def start_inquiry():
    """'Chat Seller' button on a product/seller page with no existing order.
    Reuses an existing active inquiry instead of creating duplicates."""
    seller_id = _get_seller_id()
    if not seller_id:
        flash("The seller is not available right now.", "danger")
        return redirect(request.referrer or url_for("pages.home"))

    existing = Conversation.query.filter_by(
        customer_id=current_user.id, seller_id=seller_id,
        conversation_type="INQUIRY", status="ACTIVE",
    ).order_by(Conversation.created_at.desc()).first()

    if existing:
        existing.refresh_expiration()

    if existing and existing.status == "ACTIVE":
        convo = existing
    else:
        convo = Conversation.new_inquiry(current_user.id, seller_id)

    initial_message = request.form.get("message", "").strip()
    if initial_message:
        db.session.add(Message(conversation_id=convo.id, sender_id=current_user.id, message=initial_message))
        convo.last_message_at = db.func.now()
        db.session.commit()

    return redirect(url_for("chat.view_conversation", conversation_id=convo.id))


@chat_bp.route("/<int:conversation_id>")
@login_required
def view_conversation(conversation_id):
    convo = Conversation.query.get_or_404(conversation_id)
    _authorize(convo)
    convo.refresh_expiration()
    return render_template("chat/conversation.html", convo=convo)


@chat_bp.route("/<int:conversation_id>/send", methods=["POST"])
@login_required
def send_message(conversation_id):
    convo = Conversation.query.get_or_404(conversation_id)
    _authorize(convo)
    convo.refresh_expiration()

    if convo.status != "ACTIVE":
        flash("Your inquiry has expired. Please start a new one.", "warning")
        return redirect(url_for("chat.view_conversation", conversation_id=convo.id))

    text = request.form.get("message", "").strip()
    if text:
        db.session.add(Message(conversation_id=convo.id, sender_id=current_user.id, message=text))
        from datetime import datetime
        convo.last_message_at = datetime.utcnow()
        db.session.commit()

    return redirect(url_for("chat.view_conversation", conversation_id=convo.id))


@chat_bp.route("/<int:conversation_id>/messages.json")
@login_required
def poll_messages(conversation_id):
    """Lightweight polling endpoint so the chat page can refresh without
    needing WebSockets/Socket.IO or extra infrastructure like Redis."""
    convo = Conversation.query.get_or_404(conversation_id)
    _authorize(convo)
    convo.refresh_expiration()
    return jsonify({
        "status": convo.status,
        "messages": [
            {
                "sender_id": m.sender_id,
                "sender_name": m.sender.name,
                "is_me": m.sender_id == current_user.id,
                "message": m.message,
                "created_at": m.created_at.strftime("%b %d, %I:%M %p"),
            }
            for m in convo.messages
        ],
    })
