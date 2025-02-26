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
  const storage = new StorageStack(app, 'TmOpenMatchMakingBotStack-Storage-dev', {
    env: env,
    stage: 'dev',
    account: env.account,
  })
  // NOTE this costs significant money, keep it commented out when not testing changes to the deployed service
  // new BotServiceStack(app, 'TmOpenMatchMakingBotStack-BotService-dev', {
  //   env: env,
  //   stage: 'dev',
  //   secretsBucket: storage.secretsBucket,
  //   playerProfilesTable: storage.playerProfilesTable,
  //   playerElosTable: storage.playerElosTable,
  //   matchResultsTable: storage.matchResultsTable,
  //   matchQueuesTable: storage.matchQueuesTable,
  //   leaderboardsTable: storage.leaderboardsTable,
  //   ranksTable: storage.ranksTable,
  //   leaderboardRanksTable: storage.leaderboardRanksTable,
  // })
} else {
  const storage = new StorageStack(app, 'TmOpenMatchMakingBotStack-Storage-prod', {
    env: env,
    stage: 'prod',
    account: env.account,
    terminationProtection: true,
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
    leaderboardRanksTable: storage.leaderboardRanksTable,
    nextBotMatchIdTable: storage.nextBotMatchIdTable,
    activeMatchesTable: storage.activeMatchesTable,
    terminationProtection: true,
  })
}