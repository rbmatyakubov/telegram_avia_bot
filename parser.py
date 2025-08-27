import asyncio
import logging
import os
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
# Берем токен и URL из переменных окружения на Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
# -----------------

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
        "Просто напиши или скажи мне, куда и откуда ты хочешь полететь, и я открою для тебя форму поиска.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

# =================================================================
# ↓↓↓  ОСНОВНОЕ ИЗМЕНЕНИЕ НАХОДИТСЯ В ЭТОЙ ФУНКЦИИ  ↓↓↓
# =================================================================
async def process_text_and_send_link(message: Message, text: str):
    """
    Анализирует текст, формирует ссылку (с параметрами или без) и ВСЕГДА отправляет кнопку.
    """
    await message.answer("Секунду, готовлю форму поиска... 🧐")
    
    # 1. Пытаемся извлечь данные из текста
    entities = extract_entities(text)
    
    # 2. Формируем URL с параметрами (если они есть)
    params = []
    if entities.get("origin_iata"):
        params.append(f'origin_iata={entities["origin_iata"]}')
    if entities.get("destination_iata"):
        params.append(f'destination_iata={entities["destination_iata"]}')
    if entities.get("date"):
        params.append(f'depart_date={entities["date"]}')
    
    query_string = "&".join(params)
    # Если entities пустой, query_string тоже будет пустым, и ссылка получится базовой
    final_url = f"{WEB_APP_URL}?{query_string}"

    # 3. Выбираем текст сообщения и кнопки в зависимости от того, поняли ли мы запрос
    if entities.get("origin_iata") or entities.get("destination_iata"):
        # Если хоть какой-то город распознан
        message_text = "Отлично! Я предварительно заполнил форму поиска. Нажмите на кнопку, чтобы проверить."
        button_text = "✅ Открыть предзаполненную форму"
    else:
        # Если ничего не распознано
        message_text = "Я не смог распознать ваш запрос, но вы можете заполнить форму вручную. Нажмите на кнопку, чтобы открыть поиск."
        button_text = "✈️ Открыть форму поиска"

    # 4. Создаем и отправляем кнопку
    builder = InlineKeyboardBuilder()
    builder.button(text=button_text, web_app=WebAppInfo(url=final_url))
    await message.answer(message_text, reply_markup=builder.as_markup())

# =================================================================
# ↑↑↑  КОНЕЦ ИЗМЕНЕНИЙ  ↑↑↑
# =================================================================


@dp.message(F.text)
async def handle_text_message(message: Message):
    # Этот обработчик теперь просто вызывает нашу основную логику
    await process_text_and_send_link(message, message.text)


@dp.message(F.voice)
async def handle_voice_message(message: Message, bot: Bot):
    await message.answer("Получил голосовое сообщение! Расшифровываю... 🤫")
    
    # Сначала пытаемся распознать речь
    try:
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
        
        recognized_text = recognizer.recognize_google(audio_data, language="ru-RU")
        await message.answer(f"<b>Распознанный текст:</b> «{recognized_text}»", parse_mode="HTML")
        # Если распозналось, передаем текст в нашу основную логику
        await process_text_and_send_link(message, recognized_text)

    except (sr.UnknownValueError, sr.RequestError) as e:
        # Если речь не распозналась, все равно отправляем пустую форму
        logging.error(f"Ошибка распознавания речи: {e}")
        # Передаем пустую строку, чтобы гарантированно открылась пустая форма
        await process_text_and_send_link(message, "")


async def main():
    if not BOT_TOKEN or not WEB_APP_URL:
        logging.error("Не найдены переменные окружения BOT_TOKEN или WEB_APP_URL!")
        return

    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")