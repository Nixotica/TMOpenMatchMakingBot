# Open Trackmania Matchmaking Bot

This is a WIP open source project for creating a matchmaking bot in discord. 

## Development

WARNING! Deploying a stack locally can currently cost up to $10/mo. This is primarily due to the constant uptime of the ECS task.

1. Create an AWS account. (There are multiple resources online about how to do this, and it's free). 

2. Create `.env` file in `/lib/mm-bot/` and update the required variables:
    ```
        SECRETS_BUCKET=secrets.json
        PLAYER_PROFILES_TABLE=tm-mm-bot-player-profiles-dev-<account-id>
        PLAYER_ELOS_TABLE=tm-mm-bot-player-elos-dev-<account-id>
        MATCH_RESULTS_TABLE=tm-mm-bot-match-results-dev-<account-id>
        MATCH_QUEUES_TABLE=tm-mm-bot-match-queues-dev-<account-id>
        LEADERBOARDS_TABLE=tm-mm-bot-leaderboards-dev-<account-id>
        AWS_ACCESS_KEY_ID=<your-id>
        AWS_SECRET_ACCESS_KEY=<your-access-key>
        AWS_DEFAULT_REGION=<your-region>
    ```
    These will be used when you run your container locally for faster testing. 

3. Set environment variable `STAGE="dev"` on your system. This will be used to differentiate resources to deploy for prod vs development and testing. 

4. Run `cdk deploy` to deploy your stack to your AWS account. **IMPORTANT**: If you want to limit your spend, go to the AWS console and disable or terminate your ECS task and delete the flexible IP address. If you are only running the bot via your local docker container (for test or otherwise) you will not need these resources. 

5. Create a discord bot following a guide (you could follow [this one](https://www.ionos.com/digitalguide/server/know-how/creating-discord-bot/)).

6. Create `secrets.json` file anywhere, copy the snippet below, and update the required variables:
    ```
        {
            "UBI_AUTHS": ["Basic <user:pass base64>"],
            "DISCORD_BOT_TOKEN": "<token>"
        }
    ```
    For the username and password, use what you sign in with for Ubisoft, and enter it into [this website](https://www.base64decode.org/), making sure you switch to *encode* mode. For example, if you had username "my" and password "pass", type in "my:pass" and it would return "bXk6cGFzcw==", so you would set `"UBI_AUTHS": ["Basic bXk6cGFzcw=="]`. 

7. Go to S3 and upload `secrets.json` to the bucket `tm-mm-bot-secrets-dev-<account_id>` at the root directory. 

8. Ensure you've installed docker (easy to look up). 

9. Now you have a bot, the required infrastructure launched, and the code the bot will use in `/lib/mm-bot`. Navigate to `/lib/mm-bot` and run `docker-compose up --build` to build and run the bot locally. You should see output something like this:
    ```
        $ discord.client logging in using static token
        $ discord.gateway Shard ID None has connected to Gateway (Session ID: d77e6960cc3dbd8d6201ce02f47c0d3d).
    ```

10. Go to the server with the bot added to it, and try running some commands. Now you can either use it or continue to develop this bot. Enjoy!

11. To stop running the bot, you should run `docker-compose stop` from the same directory (in a separate terminal instance if your logs are being output to the first instance), which will run through the necessary tear-down steps to remove queues from the discord server channels, etc. 

## Contact

The current owner and sole contributor to this package is @Nixotica, available on most platforms via that same alias. 