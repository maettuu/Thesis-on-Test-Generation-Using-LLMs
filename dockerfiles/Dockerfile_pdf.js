FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Zurich
WORKDIR /app

# 1. System dependencies
RUN apt-get update \
    && apt-get install -y \
        software-properties-common \
        tzdata \
        git \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Node.js + latest npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# 3. Clone & Checkout
ARG commit_hash
RUN echo "Cloning commit: ${commit_hash}" \
    && git clone https://github.com/mozilla/pdf.js.git /app/testbed
WORKDIR /app/testbed
RUN git checkout ${commit_hash}

# 4. Install dependecies
RUN PUPPETEER_SKIP_DOWNLOAD=true npm ci  # necessary to skip outdated downloads (for old commits)

# 5. Append `unittest-single` task to gulpfile.mjs
RUN printf '\ngulp.task(\n' >> gulpfile.mjs \
 && printf '  "unittest-single",\n' >> gulpfile.mjs \
 && printf '  gulp.series(\n' >> gulpfile.mjs \
 && printf '    setTestEnv,\n' >> gulpfile.mjs \
 && printf '    "generic-legacy",\n' >> gulpfile.mjs \
 && printf '    "lib-legacy",\n' >> gulpfile.mjs \
 && printf '    function runSingleUnitTest(done) {\n' >> gulpfile.mjs \
 && printf '      const args = [\n' >> gulpfile.mjs \
 && printf '        "node_modules/jasmine/bin/jasmine",\n' >> gulpfile.mjs \
 && printf '        "JASMINE_CONFIG_PATH=test/unit/clitests.json",\n' >> gulpfile.mjs \
 && printf '      ];\n' >> gulpfile.mjs \
 && printf '      const filter = process.env.TEST_FILTER;\n' >> gulpfile.mjs \
 && printf '      if (filter) {\n' >> gulpfile.mjs \
 && printf '        args.push(`--filter=${filter}`);\n' >> gulpfile.mjs \
 && printf '      }\n' >> gulpfile.mjs \
 && printf '      const jasmineProcess = startNode(args, { stdio: "inherit" });\n' >> gulpfile.mjs \
 && printf '      jasmineProcess.on("close", function (code) {\n' >> gulpfile.mjs \
 && printf '        if (code !== 0) {\n' >> gulpfile.mjs \
 && printf '          done(new Error("Unit test failed."));\n' >> gulpfile.mjs \
 && printf '          return;\n' >> gulpfile.mjs \
 && printf '        }\n' >> gulpfile.mjs \
 && printf '        done();\n' >> gulpfile.mjs \
 && printf '      });\n' >> gulpfile.mjs \
 && printf '    }\n' >> gulpfile.mjs \
 && printf '  )\n' >> gulpfile.mjs \
 && printf ');\n' >> gulpfile.mjs

# 6. Success notification
CMD ["node", "-e", "console.log('environment is ready')"]
