#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { TmOpenMatchMakingBotStack } from '../lib/stack/tm_open_match_making_bot_stack';

const app = new cdk.App();
const env = {
  account: "115984396435",
  region: 'us-west-2',
}

// For local testing, make sure you've run `export STAGE=dev`
if (process.env.STAGE == 'dev') {
  new TmOpenMatchMakingBotStack(app, 'TmOpenMatchMakingBotStack-dev', {
    env: env,
    stage: 'dev',
  });
} else {
  new TmOpenMatchMakingBotStack(app, 'TmOpenMatchMakingBotStack-prod', {
    env: env,
    stage: 'prod',
  });
}