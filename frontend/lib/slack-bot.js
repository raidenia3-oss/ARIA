let app = null;
let initAttempted = false;

async function getApp() {
  if (!initAttempted) {
    initAttempted = true;
    if (process.env.SLACK_BOT_TOKEN && process.env.SLACK_SIGNING_SECRET) {
      try {
        const { App } = require("@slack/bolt");
        app = new App({
          token: process.env.SLACK_BOT_TOKEN,
          signingSecret: process.env.SLACK_SIGNING_SECRET,
        });

        app.command("/ame", async ({ ack, body, client }) => {
          await ack();
          const channelId = body.channel_id;

          try {
            await client.chat.postMessage({
              channel: channelId,
              text: "🤖 AME Assistant activated",
              blocks: [
                {
                  type: "section",
                  text: {
                    type: "mrkdwn",
                    text: "*AME Available Commands:*\n/ame analyze <text>\n/ame news\n/ame status",
                  },
                },
              ],
            });
          } catch (error) {
            console.error("Slack command error:", error);
          }
        });

        app.event("app_mention", async ({ event, client }) => {
          try {
            await client.chat.postMessage({
              channel: event.channel,
              text: `🤖 Hello <@${event.user}>! I'm AME Assistant.`,
            });
          } catch (error) {
            console.error("Slack mention error:", error);
          }
        });
      } catch (error) {
        console.error("Failed to initialize Slack app:", error);
      }
    } else {
      console.warn("Slack environment variables not configured");
    }
  }
  return app;
}

module.exports = { getApp };
