import asyncio
import logging
import os  # <-- Добавили импорт для работы с переменными окружения
from io import BytesIO

import speech_recognition as sr
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, Voice, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pydub import AudioSegment

# Импортируем нашу функцию из parser.py
from parser import extract_entities

# --- НАСТРОЙКИ ---
# Теперь мы берем токен и URL из переменных окружения.
# Это безопасно и является стандартом для хостингов.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
# --- НИКАКИХ ПРОКСИ ---

# Настройка логирования
logging.basicConfig(level=logging.INFO)

dp = Dispatcher()
recognizer = sr.Recognizer()

@dp.message(CommandStart())
async def send_welcome(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="✈️ Найти авиабилеты", web_app=WebAppInfo(url=WEB_APP_URL))
    await message.answer(
        "Привет! Я помогу тебе найти авиабилеты.\n\n"
        "Ты можешь просто написать мне запрос, например: "
        "<b>«хочу билет из Москвы в Сочи на 25 декабря»</b>\n\n"
        "Или отправь голосовое сообщение с тем же запросом!",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

async def process_text_and_send_link(message: Message, text: str):
    await message.answer("Анализирую ваш запрос... 🧐")
    entities = extract_entities(text)
    if not entities.get("origin_iata") and not entities.get("destination_iata"):
        await message.answer("К сожалению, не смог распознать города в вашем запросе. Попробуйте еще раз.")
        return
    params = []
    if entities.get("origin_iata"):
        params.append(f'origin_iata={entities["origin_iata"]}')
    if entities.get("destination_iata"):
        params.append(f'destination_iata={entities["destination_iata"]}')
    if entities.get("date"):
        params.append(f'depart_date={entities["date"]}')
    query_string = "&".join(params)
    final_url = f"{WEB_APP_URL}?{query_string}"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Открыть предзаполненную форму", web_app=WebAppInfo(url=final_url))
    await message.answer(
        "Отлично! Я разобрал ваш запрос. Нажмите на кнопку ниже, чтобы увидеть результаты.",
        reply_markup=builder.as_markup()
    )

@dp.message(F.text)
async def handle_text_message(message: Message):
    await process_text_and_send_link(message, message.text)

@dp.message(F.voice)
async def handle_voice_message(message: Message, bot: Bot):
    await message.answer("Получил голосовое сообщение! Расшифровываю... 🤫")
    voice_file_info = await bot.get_file(message.voice.file_id)
    voice_ogg = BytesIO()
    await bot.download_file(voice_file_info.file_path, voice_ogg)
    voice_ogg.seek(0)
    audio = AudioSegment.from_ogg(voice_ogg)
    voice_wav = BytesIO()
    audio.export(voice_wav, format="wav")
    voice_wav.seek(0)
    with sr.AudioFile(voice_wav) as source:
        audio_data = recognizer.record(source)
    try:
        recognized_text = recognizer.recognize_google(audio_data, language="ru-RU")
        await message.answer(f"<b>Распознанный текст:</b> «{recognized_text}»", parse_mode="HTML")
        await process_text_and_send_link(message, recognized_text)
    except sr.UnknownValueError:
        await message.answer("Извините, не смог разобрать речь. Попробуйте еще раз.")
    except sr.RequestError as e:
        await message.answer(f"Ошибка сервиса распознавания; {e}")

async def main():
    if not BOT_TOKEN or not WEB_APP_URL:
        logging.error("Не найдены переменные окружения BOT_TOKEN или WEB_APP_URL!")
        return

    # Простая инициализация бота без прокси и сложных сессий
    bot = Bot(token=BOT_TOKEN)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")