from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from extensions import db
from models import Conversation, Message, User, CHAT_OPEN_STATUSES
from utils import safe_redirect_target

chat_bp = Blueprint("chat", __name__)

MAX_MESSAGE_LENGTH = 2000


def _get_seller_id():
    admin = User.query.filter_by(role="admin").first()
    return admin.id if admin else None


def _authorize(conversation):
    # Main admin and moderators can review/respond to any seller conversation.
    if current_user.is_admin:
        return
    if conversation.customer_id != current_user.id:
        abort(403)


@chat_bp.route("/")
@login_required
def conversations():
    """Customer's own conversation list. Admins use /admin/chats instead."""
    Conversation.expire_stale_inquiries()
    convos = Conversation.query.filter_by(customer_id=current_user.id) \
        .order_by(Conversation.last_message_at.desc()).all()
    active = [c for c in convos if c.status in CHAT_OPEN_STATUSES]
    others = [c for c in convos if c.status not in CHAT_OPEN_STATUSES]
    return render_template("chat/conversations.html", active=active, others=others)


# GET is allowed on purpose: an anonymous visitor who clicks "Chat Seller" is
# sent to the login page with ?next=/chat/start-inquiry, and after logging in
# the browser comes back with a GET. With POST only that ended in a 405 error.
# The action is idempotent (an open inquiry is reused), so GET is safe.
@chat_bp.route("/start-inquiry", methods=["GET", "POST"])
@login_required
def start_inquiry():
    """'Chat Seller' button on a product/seller page with no existing order.
    Reuses an existing open inquiry instead of creating duplicates."""
    seller_id = _get_seller_id()
    if not seller_id:
        flash("The seller is not available right now.", "danger")
        return redirect(safe_redirect_target(request.referrer, url_for("pages.home")))

    Conversation.expire_stale_inquiries()

    # New inquiries are created as PENDING (legacy rows may still say ACTIVE).
    # The old code searched for PENDING only while creating ACTIVE rows, so
    # it never found anything and made a new inquiry on every click.
    existing = Conversation.query.filter(
        Conversation.customer_id == current_user.id,
        Conversation.seller_id == seller_id,
        Conversation.conversation_type == "INQUIRY",
        Conversation.status.in_(CHAT_OPEN_STATUSES),
    ).order_by(Conversation.created_at.desc()).first()

    convo = existing or Conversation.new_inquiry(current_user.id, seller_id)

    initial_message = request.form.get("message", "").strip()[:MAX_MESSAGE_LENGTH]
    if initial_message:
        db.session.add(Message(conversation_id=convo.id, sender_id=current_user.id, message=initial_message))
        convo.last_message_at = datetime.utcnow()
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

    if not convo.is_open:
        flash("This conversation is closed. Please start a new inquiry if you need help.", "warning")
        return redirect(url_for("chat.view_conversation", conversation_id=convo.id))

    text = request.form.get("message", "").strip()
    if len(text) > MAX_MESSAGE_LENGTH:
        flash(f"Messages are limited to {MAX_MESSAGE_LENGTH} characters.", "warning")
        return redirect(url_for("chat.view_conversation", conversation_id=convo.id))

    if text:
        db.session.add(Message(conversation_id=convo.id, sender_id=current_user.id, message=text))
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

    # Load senders in the same query (the old loop issued one extra query per
    # message on every 5-second poll).
    messages = (
        Message.query.options(joinedload(Message.sender))
        .filter_by(conversation_id=convo.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    return jsonify({
        "status": convo.status,
        "messages": [
            {
                "sender_id": m.sender_id,
                "sender_name": m.sender.name,
                "is_me": m.sender_id == current_user.id,
                "message": m.message,
                "created_at": m.created_at.strftime("%b %d, %I:%M %p") if m.created_at else "",
            }
            for m in messages
        ],
    })
