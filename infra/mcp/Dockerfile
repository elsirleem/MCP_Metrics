FROM mirror.gcr.io/library/node:20-alpine

WORKDIR /usr/src/app

# Fetch source via git (public repo)
RUN apk add --no-cache git \
	&& git clone https://github.com/modelcontextprotocol/github-mcp-server.git .

# Install dependencies; fall back to npm install if no lockfile
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

EXPOSE 3001
CMD ["npm", "run", "start"]
