import { NextRequest, NextResponse } from "next/server";
import { bot } from "../../../../lib/telegram-bot";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      message?: { text?: string; chat: { id: number | string } };
      callback_query?: { id: string; data?: string; message: { chat: { id: number | string } } };
    };

    if (!process.env.TELEGRAM_BOT_TOKEN) {
      return NextResponse.json({ ok: true, message: "Telegram bot not configured (mock response)" });
    }

    if (body.message) {
      const text = body.message.text || "";
      const chatId = body.message.chat.id;

      if (text.startsWith("/ame")) {
        await bot.telegram.sendMessage(chatId, "AME Commands:\n/analyze\n/news\n/status");
      } else {
        await bot.telegram.sendMessage(chatId, `Processing: ${text}`);
      }
    }

    if (body.callback_query) {
      const chatId = body.callback_query.message.chat.id;
      const action = body.callback_query.data;
      await bot.telegram.answerCbQuery(body.callback_query.id);
      await bot.telegram.sendMessage(chatId, `Action received: ${action}`);
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Telegram webhook error:", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({ status: "Telegram webhook endpoint active" });
}
