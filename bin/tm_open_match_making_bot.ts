#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { StorageStack } from '../lib/stack/storage';
import { BotServiceStack } from '../lib/stack/bot_service';

const app = new cdk.App();
const env = {
  account: "115984396435",
  region: 'us-west-2',
}

// For local testing, make sure you've run `export STAGE=dev`
if (process.env.STAGE == 'dev') {
  new StorageStack(app, 'TmOpenMatchMakingBotStack-Storage-dev', {
    env: env,
    stage: 'dev',
    account: env.account,
  })
} else {
  const storage = new StorageStack(app, 'TmOpenMatchMakingBotStack-Storage-prod', {
    env: env,
    stage: 'prod',
    account: env.account,
  })
  new BotServiceStack(app, 'TmOpenMatchMakingBotStack-BotService-prod', {
    env: env,
    stage: 'prod',
    secretsBucket: storage.secretsBucket,
    playerProfilesTable: storage.playerProfilesTable,
    playerElosTable: storage.playerElosTable,
    matchResultsTable: storage.matchResultsTable,
    matchQueuesTable: storage.matchQueuesTable,
    leaderboardsTable: storage.leaderboardsTable,
    ranksTable: storage.ranksTable,
  })
}