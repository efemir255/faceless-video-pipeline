from setuptools import setup, find_packages

setup(
    name="faceless-video-pipeline",
    version="0.1.0",
    packages=find_packages(),
    py_modules=["config", "tts_engine", "video_fetcher", "video_engine", "uploader", "app"],
    install_requires=[
        "edge-tts>=6.1.0",
        "mutagen>=1.47.0",
        "moviepy>=2.2.1",
        "requests>=2.31.0",
        "streamlit>=1.30.0",
        "playwright>=1.40.0",
        "Pillow>=10.0.0",
        "python-dotenv>=1.0.0",
        "nest-asyncio>=1.5.0",
        "setuptools>=61.0",
    ],
)
