import os
import telebot
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import gtts
import pdfplumber
from rembg import remove
import speech_recognition
from pydub import AudioSegment
from PIL import Image
from telebot.types import ReplyKeyboardMarkup, KeyboardButton


load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)


def transform_image(filename):
    """Функция обработки изображения"""
    # Считаем изображение с помощью Image.open
    source_image = Image.open(filename)
    # Можно использовать фильтр в ч/б фото: ImageFilter.EDGE_ENHANCE
    # enhanced_image = source_image.filter(ImageFilter.EDGE_ENHANCE)

    enhanced_image = remove(source_image, bgcolor=(255, 255, 255, 255))

    # Конвертируем RGBA в RGB или L для сохранения в JPEG
    enhanced_image = enhanced_image.convert('RGB')
    # width = enhanced_image.size[0]
    # height = enhanced_image.size[1]
    # enhanced_image = enhanced_image.resize((width // 2, height // 2))
    # Сохраним изображение
    enhanced_image.save(filename)

    return filename

# Телеграм включает в сообщение 5 версий изображения.
# Максимальное качество - в последнем изображении в списке,
# поэтому для скачивания мы берем идентификатор из объекта message.photo[-1]


# ↓↓↓ Пусть функция реагирует на изображения
@bot.message_handler(content_types=['photo'])
def resend_photo(message):
    """Функция отправки обработанного изображения"""
    file_id = message.photo[-1].file_id
    filename = download_file(bot, file_id)
    # Трансформируем изображение
    transform_image(filename)
    # Открываем изображение из файла с помощью функции open, 'rb' = read bytes
    image = open(filename, 'rb')

    # Отправляем изображение в чат с пользователем
    bot.send_photo(message.chat.id, image)
    # Закрываем файл
    image.close()

    # Удаляет ненужные изображения
    if os.path.exists(filename):
        os.remove(filename)


def pdf_to_mp3(filename, language='ru'):
    """Функция конвертации pdf в mp3"""
    with pdfplumber.PDF(open(file=filename, mode='rb')) as pdf:
        pages = [page.extract_text() for page in pdf.pages]

    text = ''.join(pages)
    text = text.replace('\n', ' ')
    my_audio = gtts.gTTS(text=text, lang=language, slow=False)
    my_audio.save('file.mp3')
    return 'file.mp3'


# ↓↓↓ Пусть функция реагирует на файл
@bot.message_handler(content_types=['document'])
def converting(message):
    """Функция, отправляющая mp3 в ответ на pdf"""
    filename = download_file(bot, message.document.file_id)

    if Path(filename).is_file() and Path(filename).suffix == '.pdf':
        # Распознаем файл с помощью нашей функции pdf_to_mp3
        mp3 = pdf_to_mp3(filename, language='ru')

        audio = open(mp3, 'rb')
        # Отправляем пользователю в ответ mp3
        bot.send_audio(message.chat.id, audio)
        audio.close()

        # Удаляет ненужные файлы
        if os.path.exists(mp3):
            os.remove(mp3)

    else:
        bot.send_message(message.chat.id, 'Неверный формат файла, \nпопробуй еще раз 😜')


def oga2wav(filename):
    """Конвертация формата файлов"""
    # Переименование формата: 'sample.oga' -> 'sample.wav'
    new_filename = filename.replace('.oga', '.wav')
    # Читаем файл с диска с помощью функции AudioSegment.from_file()
    audio = AudioSegment.from_file(filename)
    # Экспортируем файл в новом формате
    audio.export(new_filename, format='wav')

    return new_filename


def recognize_speech(oga_filename):
    """Перевод голоса в текст + удаление использованных файлов"""
    wav_filename = oga2wav(oga_filename)
    recognizer = speech_recognition.Recognizer()

    with speech_recognition.WavFile(wav_filename) as source:
        wav_audio = recognizer.record(source)

    text = recognizer.recognize_google(wav_audio, language='ru')

    if os.path.exists(oga_filename):
        os.remove(oga_filename)
    if os.path.exists(wav_filename):
        os.remove(wav_filename)

    return text


# ↓↓↓ Пусть функция реагирует на голос
@bot.message_handler(content_types=['voice'])
def transcript(message):
    """Функция, отправляющая текст в ответ на голосовое"""
    # id файла - в message.voice.file_id
    filename = download_file(bot, message.voice.file_id)
    # Распознаем запись с помощью нашей функции recognize_speech
    text = recognize_speech(filename)
    # Отправляем пользователю в ответ текст
    bot.send_message(message.chat.id, text)


def download_file(bot, file_id):
    """Скачивание файла, который прислал пользователь"""
    # Получаем информацию о файле с помощью функции bot.get_file
    file_info = bot.get_file(file_id)
    # загружаем файл с помощью функции bot.download_file
    downloaded_file = bot.download_file(file_info.file_path)
    # Имя файла делаем уникальным: id файла + file_info.file_path
    filename = file_id + file_info.file_path
    # file_info.file_path имеет вид voice/file_123.oga,
    # чтобы избежать ошибок из-за косой черты, заменим ее на _
    filename = filename.replace('/', '_')

    with open(filename, 'wb') as f:
        f.write(downloaded_file)
    return filename


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "Вот, что я умею:\n"
                                      "\n"
                                      "1. Удалять фон c изображения, загрузи изображение и нажми отправить.\n"
                                      "2. Конвертировать голос в текст, запиши голос на диктофон.\n"
                                      "3. Конвертировать PDF в mp3, загрузи pdf файл и нажми отправить.\n"
                                      "\nЕсли я не работаю 😞, свяжись с моим создателем 🙈- @IgorKovalev")


def help_keyboard() -> ReplyKeyboardMarkup:
    """
    Создаёт клавиатуру с основными командами бота
    :return: keyboard
    :rtype: ReplyKeyboardMarkup
    """

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    help_button = KeyboardButton('/help')

    keyboard.row(help_button)

    return keyboard


@bot.message_handler(commands=['start'])
def say_hi(message):

    # Подключаемся к БД, создаем табл. и добавляем нового пользователя
    connect = sqlite3.connect('user.db')
    cursor = connect.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER,
        username TEXT,
        first_name TEXT,
        last_name TEXT
    )""")
    connect.commit()
    chat = message.chat
    cursor.execute('SELECT id FROM users WHERE id == ?', (chat.id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users VALUES(?,?,?,?);", (chat.id, chat.username, chat.first_name, chat.last_name))
        connect.commit()

    # Функция, отправляющая "Привет" в ответ на команду /start
    if message.from_user.last_name == None:
        bot.send_message(
            message.chat.id, f'Привет, {message.from_user.first_name}!\n' 
                             f'Я бот, чтобы посмотреть, что я умею, нажмите /help', reply_markup=help_keyboard())
    else:
        bot.send_message(
            message.chat.id, f'Привет, {message.from_user.first_name} {message.from_user.last_name}!\n'
                             f'Я бот, чтобы посмотреть, что я умею, нажмите /help', reply_markup=help_keyboard())


bot.polling()
