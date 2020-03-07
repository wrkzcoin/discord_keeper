FROM python

RUN pip install click munch pyyaml timeago discord

COPY . /usr/app/src

CMD python3 /usr/app/src/WrkzdBot.py


