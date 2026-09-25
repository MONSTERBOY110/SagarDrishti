# SagarDrishti web client. Build from the REPOSITORY ROOT:
#   docker build -f apps/web/Dockerfile .
#
# THE TWO BASES ARE BUILD ARGUMENTS, NOT RUNTIME VARIABLES. Next inlines every
# NEXT_PUBLIC_* value into the bundle when it builds, so setting one on
# `next start` changes nothing: the browser keeps calling whatever was baked
# in. This cost a real debugging session once (see playwright.config.ts). They
# are the addresses the BROWSER uses, which is why they are localhost ports and
# not the compose service names.

FROM node:22-slim

ARG NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
ARG NEXT_PUBLIC_AGENT_BASE=http://127.0.0.1:8010
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_AGENT_BASE=$NEXT_PUBLIC_AGENT_BASE \
    NEXT_TELEMETRY_DISABLED=1

RUN corepack enable && corepack prepare pnpm@10.34.5 --activate

WORKDIR /srv/sagardrishti

# Manifests first, so a source edit does not throw away the dependency layer.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/scene/package.json packages/scene/package.json
COPY apps/web/scripts apps/web/scripts
# --ignore-scripts here, and the Cesium copy run explicitly below once the
# package is present: postinstall would otherwise run before public/ exists.
RUN pnpm install --frozen-lockfile --filter @sagardrishti/web... --ignore-scripts

COPY packages/scene packages/scene
COPY apps/web apps/web

# The globe's Workers, Assets and Widgets, vendored into public/cesium so the
# scene needs no network and no Cesium ion token (ADR-0001). In the image as
# much as on a laptop: a container that fetched Cesium at runtime would break
# the air-gapped demo the first time it ran somewhere without internet.
RUN node apps/web/scripts/copy-cesium.mjs \
 && pnpm --filter @sagardrishti/web exec next build

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["pnpm", "--filter", "@sagardrishti/web", "exec", "next", "start", "-p", "3000", "-H", "0.0.0.0"]
