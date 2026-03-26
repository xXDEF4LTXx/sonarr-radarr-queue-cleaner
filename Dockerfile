FROM python:3.9-slim-buster

ENV SONARR_URL='http://sonarr:8989'
ENV SONARR_API_KEY=123456
ENV RADARR_URL='http://radarr:7878'
ENV RADARR_API_KEY=123456
ENV API_TIMEOUT=600
ENV STRIKE_COUNT=5
ENV QBITTORRENT_URL='http://qbittorrent:8080'
ENV QBITTORRENT_USERNAME=admin
ENV QBITTORRENT_PASSWORD=admin
ENV QBITTORRENT_METADATA_TIMEOUT=600

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "cleaner.py"]
