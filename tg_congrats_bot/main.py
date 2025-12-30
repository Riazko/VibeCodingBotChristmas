import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from db import (
    init_db,
    upsert_user,
    get_user_id_by_username,
    save_message,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ───────── FSM ─────────
class SendState(StatesGroup):
    waiting_username = State()
    waiting_type = State()
    waiting_text = State()
    blocked = State()  # ✅ после 1 сообщения "закрываем" любые дальнейшие тексты


# ───────── Клавиатура выбора типа ─────────
def type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔒 Анонимно")],
            [KeyboardButton(text="👀 С указанием отправителя")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ───────── /start ─────────
@dp.message(Command("start"))
async def start(message: Message):
    await upsert_user(message.from_user)
    await message.answer(
        "👋 Привет!\n\n"
        "Чтобы отправить поздравление — напиши /send"
    )


# ───────── /send ─────────
@dp.message(Command("send"))
async def send(message: Message, state: FSMContext):
    await upsert_user(message.from_user)
    await state.clear()
    await state.set_state(SendState.waiting_username)
    await message.answer("Введи @username получателя 👇", reply_markup=ReplyKeyboardRemove())


# ───────── Ввод username ─────────
@dp.message(SendState.waiting_username)
async def get_username(message: Message, state: FSMContext):
    username = (message.text or "").strip()

    if not username.startswith("@"):
        await message.answer("❌ Username должен начинаться с @")
        return

    recipient_id = await get_user_id_by_username(username)

    if not recipient_id:
        await message.answer(
            "❌ Пользователь не найден.\n"
            "Он должен нажать /start в этом боте."
        )
        return

    if recipient_id == message.from_user.id:
        await message.answer("❌ Нельзя отправить сообщение самому себе")
        return

    await state.update_data(recipient_id=recipient_id)
    await state.set_state(SendState.waiting_type)
    await message.answer("Выбери тип поздравления:", reply_markup=type_keyboard())


# ───────── Выбор типа ─────────
@dp.message(SendState.waiting_type)
async def get_type(message: Message, state: FSMContext):
    if message.text not in ("🔒 Анонимно", "👀 С указанием отправителя"):
        await message.answer("Выбери вариант с кнопок ниже ⬇️")
        return

    await state.update_data(is_anonymous=(message.text == "🔒 Анонимно"))
    await state.set_state(SendState.waiting_text)
    await message.answer("✍️ Напиши текст поздравления", reply_markup=ReplyKeyboardRemove())


# ───────── Ввод текста (ТОЛЬКО 1 сообщение) ─────────
@dp.message(SendState.waiting_text)
async def get_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Сообщение не может быть пустым")
        return

    # ✅ СРАЗУ "запираем" пользователя, чтобы следующие сообщения не попали сюда
    await state.set_state(SendState.blocked)

    data = await state.get_data()
    recipient_id = data["recipient_id"]
    is_anonymous = data["is_anonymous"]

    sender = message.from_user
    sender_name = f"@{sender.username}" if sender.username else sender.full_name

    if is_anonymous:
        final_text = (
            "🎁 Тебе пришло анонимное поздравление:\n\n"
            f"{text}\n\n"
            "— отправитель скрыт"
        )
    else:
        final_text = (
            "🎁 Тебе пришло поздравление:\n\n"
            f"{text}\n\n"
            f"— от {sender_name}"
        )

    try:
        await bot.send_message(recipient_id, final_text)
    except Exception as e:
        print("❌ ОШИБКА ОТПРАВКИ:", e)
        await state.clear()
        await message.answer(
            "❌ Не удалось доставить поздравление.\n"
            "Возможно, получатель не запускал бота или заблокировал его.\n\n"
            "👉 Чтобы отправить поздравление другому пользователю — напишите /send"
        )
        return

    await save_message(
        sender_id=sender.id,
        recipient_id=recipient_id,
        text=text,
        is_anonymous=is_anonymous,
    )

    # ✅ выходим из сценария полностью
    await state.clear()

    await message.answer(
        "✅ Поздравление отправлено 🎉\n\n"
        "👉 Чтобы отправить поздравление другому пользователю — напишите снова /send"
    )


# ───────── Любые сообщения в blocked: жестко прерываем ─────────
@dp.message(SendState.blocked)
async def blocked(message: Message, state: FSMContext):
    await message.answer(
        "ℹ️ Ты уже отправил поздравление.\n"
        "👉 Чтобы отправить другое — напиши /send"
    )


# ───────── Любые сообщения вне FSM (не /команды) ─────────
@dp.message()
async def outside_flow(message: Message, state: FSMContext):
    # если пользователь не в сценарии — подсказка
    if await state.get_state() is None and not (message.text or "").startswith("/"):
        await message.answer("ℹ️ Чтобы отправить поздравление — напиши /send")


# ───────── Запуск ─────────
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
