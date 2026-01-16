FROM mirror.gcr.io/library/node:20-alpine

WORKDIR /usr/src/app

COPY server.js ./

RUN npm install express axios body-parser

EXPOSE 3001

CMD ["node", "server.js"]