const { Client, IntentsBitField, REST, Routes } = require("discord.js");

if (!process.env.DISCORD_TOKEN || !process.env.DISCORD_CLIENT_ID) {
  console.warn("Discord environment variables not configured");
}

const client = new Client({
  intents: [
    IntentsBitField.Flags.Guilds,
    IntentsBitField.Flags.GuildMessages,
    IntentsBitField.Flags.MessageContent,
  ],
});

const commands = [
  {
    name: "ame",
    description: "Activar AME Assistant",
    options: [
      {
        name: "action",
        type: 3,
        description: "Acción: analyze, news, status",
        required: true,
      },
    ],
  },
];

client.once("ready", () => {
  console.log("✅ Discord bot ready");

  if (process.env.DISCORD_TOKEN && process.env.DISCORD_CLIENT_ID) {
    const rest = new REST().setToken(process.env.DISCORD_TOKEN);
    rest
      .put(Routes.applicationCommands(process.env.DISCORD_CLIENT_ID), {
        body: commands,
      })
      .then(() => console.log("✅ Discord commands registered"))
      .catch((error) => console.error("Discord command registration error:", error));
  }
});

client.on("interactionCreate", async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  if (interaction.commandName === "ame") {
    await interaction.reply({
      embeds: [
        {
          title: "🤖 AME Assistant",
          description: "Ready to assist",
          color: 0xDC143C,
        },
      ],
    });
  }
});

module.exports = { client, commands };
