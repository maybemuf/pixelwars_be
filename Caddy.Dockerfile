# Pinned by digest: xcaddy rebuilds from source, so a moving base tag would silently
# change the proxy binary.
FROM caddy:builder-alpine@sha256:1a1689db91cfb390b2d856a1b3774e796852822cd723fa54c475b272f82bb4b7 AS builder

RUN xcaddy build \
		--with github.com/mholt/caddy-ratelimit

FROM caddy:alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
