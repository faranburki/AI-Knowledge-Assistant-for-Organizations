import pyttsx3
import os

engine = pyttsx3.init()
engine.setProperty('rate', 150)

os.makedirs('Backend/scripts/test_audio', exist_ok=True)

test_cases = {
    '2s_hello.wav': "Hello, this is a short two second greeting.",
    '5s_menu_query.wav': "Hello there. Can you please tell me what is on the menu for today at the restaurant?",
    '10s_long_query.wav': "Hi. I was wondering if you could provide me with a comprehensive breakdown of all the services that the clinic provides, including any specialists that might be available on weekends, because I need to schedule an appointment soon.",
    'isolation_restaurant.wav': "What is on the restaurant menu?",
    'isolation_clinic.wav': "What medical services does the clinic provide?"
}

for filename, text in test_cases.items():
    filepath = os.path.join('Backend', 'scripts', 'test_audio', filename)
    engine.save_to_file(text, filepath)

engine.runAndWait()
print("✅ Generated test audio files in Backend/scripts/test_audio/")
