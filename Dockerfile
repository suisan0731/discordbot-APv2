FROM python:3.11
WORKDIR /bot
COPY . /bot
RUN pip install -r requirements.txt
RUN curl -OL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
RUN tar -xf ffmpeg-release-amd64-static.tar.xz
RUN rm ffmpeg-release-amd64-static.tar.xz
RUN tar -xf libopus.tar.gz
RUN rm libopus.tar.gz
CMD python3 main.py