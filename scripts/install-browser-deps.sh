#!/bin/bash
set -e

echo "🚀 Instalando dependencias de Browser Automation"

cd frontend

# Browser Automation
npm install --save puppeteer puppeteer-extra puppeteer-extra-plugin-stealth
npm install --save playwright @playwright/test
npm install --save selenium-webdriver

# Scraping & DOM
npm install --save cheerio jsdom

# Firebase & Google
npm install --save firebase-admin @google-cloud/storage @google-cloud/firestore
npm install --save googleapis

# Automation
npm install --save node-cron bull redis
npm install --save nodemailer

# Database
npm install --save @neondatabase/serverless @prisma/client prisma
npm install --save pg

# Utilities
npm install --save axios lodash dotenv crypto

echo "✅ Todas las dependencias instaladas"