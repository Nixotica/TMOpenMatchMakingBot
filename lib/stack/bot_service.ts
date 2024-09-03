import { CfnOutput } from "aws-cdk-lib";
import { Table } from "aws-cdk-lib/aws-dynamodb";
import { AmazonLinuxCpuType, AmazonLinuxGeneration, CloudFormationInit, InitCommand, InitFile, InitService, InitSource, Instance, InstanceClass, InstanceSize, InstanceType, MachineImage, Peer, Port, SecurityGroup, ServiceManager, Vpc } from "aws-cdk-lib/aws-ec2";
import { DockerImageAsset } from "aws-cdk-lib/aws-ecr-assets";
import { AwsLogDriver, Cluster, ContainerImage, FargateService, FargateTaskDefinition } from "aws-cdk-lib/aws-ecs";
import { ApplicationLoadBalancedFargateService } from "aws-cdk-lib/aws-ecs-patterns";
import { PolicyStatement, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { Bucket } from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";
import path = require("path");

export interface BotServiceConstructProps {
    /** The stage of this stack (dev, prod). */
    stage: string,

    /** A bucket containing secrets used by the bot during runtime. */
    secretsBucket: Bucket,

    /** A table containing player specific information. */
    playerProfilesTable: Table,

    /** A table containing match results. */
    matchResultsTable: Table,
}

/**
 * A construct for deploying a container to host the bot. 
 */
export class BotServiceConstruct extends Construct {
    constructor(scope: Construct, id: string, props: BotServiceConstructProps) {
        super(scope, id);

        /**
         * VPC 
         */
        const vpc = new Vpc(this, 'MM-Bot-VPC', {
            maxAzs: 1,
        });

        /**
         * ECS Cluster
         */
        const cluster = new Cluster(this, 'MM-Bot-Cluster', {
            vpc,
        });
  
        // Build and push the Docker image to an ECR repository
        const dockerImageAsset = new DockerImageAsset(this, 'MM-Bot-Image', {
            directory: path.join(__dirname, '../mm-bot'), // Path to your Dockerfile directory
        });
    
        // Define a task role
        const taskRole = new Role(this, 'MM-Bot-TaskRole', {
            assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
        });
        props.secretsBucket.grantRead(taskRole);
        props.playerProfilesTable.grantFullAccess(taskRole);
        props.matchResultsTable.grantFullAccess(taskRole);

        // Define the Fargate task with container details
        const fargateTaskDefinition = new FargateTaskDefinition(this, 'MM-Bot-Task', {
            memoryLimitMiB: 512,
            cpu: 256,
            taskRole: taskRole,
        });
    
        const container = fargateTaskDefinition.addContainer('MM-Bot-Container', {
            image: ContainerImage.fromDockerImageAsset(dockerImageAsset),
            logging: new AwsLogDriver({
                streamPrefix: 'MMBot',
            }),
            environment: {
                SECRETS_BUCKET: props.secretsBucket.bucketName,
                PLAYER_PROFILES_TABLE: props.playerProfilesTable.tableName,
                MATCH_RESULTS_TABLE: props.matchResultsTable.tableName
            }
        });
    
        container.addPortMappings({
            containerPort: 80, // Match this with the port exposed in Dockerfile
        });
    
        // Create a Fargate service without an ALB
        // TODO - look into Ec2TaskDefinition and Ec2Service on t4g nano reduce costs further
        const fargateService = new FargateService(this, 'MM-Bot-Service', {
            cluster,
            taskDefinition: fargateTaskDefinition,
            desiredCount: 0, // TODO - change back to 1 for prod 
            assignPublicIp: true, // Assign a public IP to the task
        });
    }
}