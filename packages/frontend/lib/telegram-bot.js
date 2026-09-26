const { Telegraf } = require("telegraf");

if (!process.env.TELEGRAM_BOT_TOKEN) {
  console.warn("Telegram environment variables not configured");
}

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);

bot.start((ctx) => {
  ctx.reply("🤖 Welcome to AME Assistant", {
    reply_markup: {
      inline_keyboard: [
        [{ text: "Analyze", callback_data: "analyze" }],
        [{ text: "News", callback_data: "news" }],
        [{ text: "Status", callback_data: "status" }],
      ],
    },
  });
});

bot.command("ame", (ctx) => {
  ctx.reply("AME Commands:\n/analyze\n/news\n/status");
});

bot.on("text", async (ctx) => {
  const text = ctx.message.text;
  ctx.reply(`Processing: ${text}`);
});

bot.on("callback_query", async (ctx) => {
  const action = ctx.callbackQuery.data;
  await ctx.answerCbQuery();
  ctx.reply(`Action received: ${action}`);
});

module.exports = { bot };
