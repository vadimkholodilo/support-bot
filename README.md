# 🤖 Support Bot

[![License](https://img.shields.io/github/license/nessshon/support-bot)](https://github.com/nessshon/support-bot/blob/main/LICENSE)
[![Telegram Bot](https://img.shields.io/badge/Bot-grey?logo=telegram)](https://core.telegram.org/bots)
[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
[![Redis](https://img.shields.io/badge/Redis-Yes?logo=redis&color=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-blue?logo=docker&logoColor=white)](https://www.docker.com/)

**Support Bot** is a specially designed Telegram bot for feedback. With built-in support for topics, all user messages
are intelligently categorized, promoting organized and streamlined discussion in your group. It provides features such
as blocking unwanted users, silent mode in topics for discreet conversations, and more. Improve group communication with
Support Bot!

**About Limits**:
<blockquote>
Specific limits are not specified in the documentation, but the community has shared some rough numbers. 
<br>
• Limit on topic creation per minute <b>~20</b>.
<br>
• Limit on the total number of topics <b>~1M</b>.
</blockquote>

<details>
<summary><b>Available bot commands for admins (DEV_USER_IDS)</b></summary>

* `/newsletter` - Open the newsletter menu.

  Use this command to initiate a newsletter for users.
  **Note**: This command works only in private chats.

* `/welcome` - Set the welcome message.

  Enter capture mode and send any message (text, photo, video, video note, ...)
  to use it as the greeting shown on `/start`. The message is stored by
  reference and copied to each user; send `/reset` to restore the default text
  or `/cancel` to abort. The stored message must not be deleted from your chat
  with the bot, otherwise the bot falls back to the default text.
  **Note**: This command works only in private chats.

</details>

<details>
<summary><b>Available bot commands in the group topics</b></summary>

* `/ban` - Block/Unblock User.

  Use this command to block or unblock a user, controlling the receipt of messages from them.

* `/silent` - Activate/Deactivate Silent Mode.

  Enable or disable silent mode to prevent messages from being sent to the user.

* `/information` - User Information.

  Receive a message containing basic information about the user.

</details>

## Usage

Dependencies are managed with [uv](https://docs.astral.sh/uv/) using `pyproject.toml` and `uv.lock`.

<details>
<summary><b>Preparation</b></summary>

1. Create a bot via [@BotFather](https://t.me/BotFather) and save the TOKEN (referred to as `BOT_TOKEN` later).
2. Create a group and enable topics in the group settings.
3. Add the created bot to the group as an admin and grant it the necessary rights to manage topics.
4. Add the bot [What's my Telegram ID?](https://t.me/my_id_bot) to the group and save the group ID (referred to
   as `BOT_GROUP_ID` later).
5. Optionally, customize the bot texts to fit your needs in the file
   named [texts](app/bot/utils/texts.py).
6. Optionally, add the language you need
   to [SUPPORTED_LANGUAGES](app/bot/utils/texts.py#L4)
   and add the appropriate codes to
   the [data](app/bot/utils/texts.py#L49).

</details>

<details>
<summary><b>Installation</b></summary>

You need your own server or you can rent one from a hosting provider. For this, check out the [Recommended Hosting Provider](#recommended-hosting-provider) section below.

1. Clone the repository:

    ```bash
    git clone https://github.com/nessshon/support-bot.git
    ```

2. Change into the bot directory:

    ```bash
    cd support-bot
    ```
3. Clone environment variables file:

   ```bash
   cp .env.example .env
   ```

4. Configure [environment variables](#environment-variables-reference) variables file:

   ```bash
   nano .env
   ```

5. Running a bot in a docker container:

   ```bash
   docker compose up --build
   ```

</details>

For local development, install [uv](https://docs.astral.sh/uv/) and run:

```bash
uv sync
docker compose up -d postgres redis
REDIS_HOST=127.0.0.1 POSTGRES_DSN=postgresql+asyncpg://support_bot:support_bot@127.0.0.1:5432/support_bot uv run python -m app
```

The Compose override publishes Redis on `127.0.0.1:6379` and PostgreSQL on
`127.0.0.1:5432`. The bot service is disabled by default in development, so the command above
starts the infrastructure and applies migrations while the bot runs directly on the host. To run the bot in a
container during development, use `docker compose --profile dev-bot up`.
The development `bot` and `migrate` services use `pull_policy: build`, so they always build from
the local Dockerfile instead of pulling the published image.

## Environment Variables Reference

<details>
<summary>Click to expand</summary>

Here is a comprehensive reference guide for the environment variables used in the project:

| Variable       | Type  | Description                                                   | Example               |
|----------------|-------|---------------------------------------------------------------|-----------------------|
| `BOT_TOKEN`    | `str` | Bot token, obtained from [@BotFather](https://t.me/BotFather) | `123456:qweRTY`       | 
| `BOT_DEV_USER_IDS` | `str` | Comma-separated user ID(s) of the bot developer(s)/admin(s)  | `123456789,987654321` |
| `BOT_GROUP_ID` | `str` | Group ID where the bot operates                               | `-100123456789`       |
| `BOT_EMOJI_ID` | `str` | The custom emoji ID for the group's topic.                    | `5417915203100613993` |
| `BOT_FF_SOURCE_TRACKING` | `bool` | Feature flag: track user acquisition source from the `/start` deep-link `src_` payload (e.g. `t.me/<bot>?start=src_twitter`). Stored in PostgreSQL and shown in the topic-created message and by the `/information` command. Defaults to off. | `false` |
| `REDIS_HOST`   | `str` | The hostname or IP address of the Redis server                | `redis`               |
| `REDIS_PORT`   | `int` | The port number on which the Redis server is running          | `6379`                |
| `REDIS_DB`     | `int` | The Redis database number                                     | `1`                   |
| `POSTGRES_DSN` | `str` | Async PostgreSQL connection string                           | `postgresql+asyncpg://support_bot:***@postgres:5432/support_bot` |

<details>
<summary>List of supporting custom emoji ID's</summary>

`5434144690511290129` - 📰

`5312536423851630001` - 💡

`5312016608254762256` - ⚡️

`5377544228505134960` - 🎙

`5418085807791545980` - 🔝

`5370870893004203704` - 🗣

`5420216386448270341` - 🆒

`5379748062124056162` - ❗️

`5373251851074415873` - 📝

`5433614043006903194` - 📆

`5357315181649076022` - 📁

`5309965701241379366` - 🔎

`5309984423003823246` - 📣

`5312241539987020022` - 🔥

`5312138559556164615` - ❤️

`5377316857231450742` - ❓

`5350305691942788490` - 📈

`5350713563512052787` - 📉

`5309958691854754293` - 💎

`5350452584119279096` - 💰

`5309929258443874898` - 💸

`5377690785674175481` - 🪙

`5310107765874632305` - 💱

`5377438129928020693` - ⁉️

`5309950797704865693` - 🎮

`5350554349074391003` - 💻

`5409357944619802453` - 📱

`5312322066328853156` - 🚗

`5312486108309757006` - 🏠

`5310029292527164639` - 💘

`5310228579009699834` - 🎉

`5377498341074542641` - ‼️

`5312315739842026755` - 🏆

`5408906741125490282` - 🏁

`5368653135101310687` - 🎬

`5310045076531978942` - 🎵

`5420331611830886484` - 🔞

`5350481781306958339` - 📚

`5357107601584693888` - 👑

`5375159220280762629` - ⚽️

`5384327463629233871` - 🏀

`5350513667144163474` - 📺

`5357121491508928442` - 👀

`5357185426392096577` - 🫦

`5310157398516703416` - 🍓

`5310262535021142850` - 💄

`5368741306484925109` - 👠

`5348436127038579546` - ✈️

`5357120306097956843` - 🧳

`5310303848311562896` - 🏖

`5350424168615649565` - ⛅️

`5413625003218313783` - 🦄

`5350699789551935589` - 🛍

`5377478880577724584` - 👜

`5310303848311562896` - 🏖

`5350424168615649565` - ⛅️

`5413625003218313783` - 🦄

`5350699789551935589` - 🛍

`5377478880577724584` - 👜

`5431492767249342908` - 🛒

`5350497316203668441` - 🚂

`5350422527938141909` - 🛥

`5418196338774907917` - 🏔

`5350648297189023928` - 🏕

`5309832892262654231` - 🤖

`5350751634102166060` - 🪩

`5377624166436445368` - 🎟

`5386395194029515402` - 🏴

`5350387571199319521` - 🗳

`5357419403325481346` - 🎓

`5368585403467048206` - 🔭

`5377580546748588396` - 🔬

`5377317729109811382` - 🎶

`5382003830487523366` - 🎤

`5357298525765902091` - 🕺

`5357370526597653193` - 💃

`5357188789351490453` - 🪖

`5348227245599105972` - 💼

`5411138633765757782` - 🧪

`5386435923204382258` - 👨

`5377675010259297233` - 👶

`5386609083400856174` - 🤰

`5368808634392257474` - 💅

`5350548830041415279` - 🏛

`5355127101970194557` - 🧮

`5386379624773066504` - 🖨

`5377494501373780436` - 👮

`5350307998340226571` - 🩺

`5310094636159607472` - 💊

`5310139157790596888` - 💉

`5377468357907849200` - 🧼

`5418115271267197333` - 🪪

`5372819184658949787` - 🛃

`5350344462612570293` - 🍽

`5384574037701696503` - 🐟

`5310039132297242441` - 🎨

`5350658016700013471` - 🎭

`5357504778685392027` - 🎩

`5350367161514732241` - 🔮

`5350520238444126134` - 🍹

`5310132165583840589` - 🎂

`5350392020785437399` - ☕️

`5350406176997646350` - 🍣

`5350403544182694064` - 🍔

`5350444672789519765` - 🍕

`5312424913615723286` - 🦠

`5417915203100613993` - 💬

`5312054580060625569` - 🎄

`5309744892677727325` - 🎃

`5238156910363950406` - ✍️

`5235579393115438657` - ⭐️

`5237699328843200968` - ✅

`5238027455754680851` - 🎖

`5238234236955148254` - 🤡

`5237889595894414384` - 🧠

`5237999392438371490` - 🦮

`5235912661102773458` - 🐈

</details>

</details>

## Contribution

We welcome your contributions! If you have ideas for improvement or have identified a bug, please create an issue or
submit a pull request.

## License

This repository is distributed under the [MIT License](LICENSE).
Feel free to use, modify, and distribute the code in accordance with the terms of the license.
