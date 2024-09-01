import { CfnOutput } from "aws-cdk-lib";
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
        taskRole.addToPolicy(new PolicyStatement({
            actions: ['s3:GetObject', 's3:ListBucket'],
            resources: [
                props.secretsBucket.bucketArn,
                `${props.secretsBucket.bucketArn}/*`,
            ],
        }));

        // Define the Fargate task with container details
        const fargateTaskDefinition = new FargateTaskDefinition(this, 'MM-Bot-Task', {
            memoryLimitMiB: 512,
            cpu: 256,
        });
    
        const container = fargateTaskDefinition.addContainer('MM-Bot-Container', {
            image: ContainerImage.fromDockerImageAsset(dockerImageAsset),
            logging: new AwsLogDriver({
            streamPrefix: 'MMBot',
            }),
            environment: {
                SECRETS_BUCKET: props.secretsBucket.bucketName,
            }
        });
    
        container.addPortMappings({
            containerPort: 80, // Match this with the port exposed in Dockerfile
        });
    
        // Create a Fargate service without an ALB
        const fargateService = new FargateService(this, 'MM-Bot-Service', {
            cluster,
            taskDefinition: fargateTaskDefinition,
            desiredCount: 1, // Only one task running
            assignPublicIp: true, // Assign a public IP to the task
        });
    }
}