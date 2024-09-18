import { CfnOutput } from "aws-cdk-lib";
import { AutoScalingGroup } from "aws-cdk-lib/aws-autoscaling";
import { Table } from "aws-cdk-lib/aws-dynamodb";
import { AmazonLinuxCpuType, AmazonLinuxGeneration, CloudFormationInit, InitCommand, InitFile, InitService, InitSource, Instance, InstanceClass, InstanceSize, InstanceType, LaunchTemplate, MachineImage, Peer, Port, SecurityGroup, ServiceManager, SubnetType, Vpc } from "aws-cdk-lib/aws-ec2";
import { DockerImageAsset } from "aws-cdk-lib/aws-ecr-assets";
import { AsgCapacityProvider, AwsLogDriver, Cluster, ContainerImage, Ec2Service, Ec2TaskDefinition, FargateService, FargateTaskDefinition, Protocol } from "aws-cdk-lib/aws-ecs";
import { ApplicationLoadBalancedFargateService } from "aws-cdk-lib/aws-ecs-patterns";
import { ManagedPolicy, PolicyStatement, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
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

    /** A table containing available matchmaking queues. */
    matchQueuesTable: Table,
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
         * Security Group
         */
        const securityGroup = new SecurityGroup(this, 'MM-Bot-SG', {
            vpc,
            description: 'Allow ECS instances to communicate with ECS control plane and other APIs',
            allowAllOutbound: true, // Allow all outbound traffic
        });

        // Allow inbound SSH traffic from EC2 Instance Connect IP range (replace with your region's IP range)
        securityGroup.addIngressRule(
            Peer.ipv4('18.237.140.160/29'), // This is the range for EC2 Instance Connect in the Oregon region
            Port.tcp(22),
            'Allow SSH access for EC2 Instance Connect'
        );

        /**
         * ECS Cluster
         */
        const cluster = new Cluster(this, 'MM-Bot-Cluster', {
            vpc,
        });
        const instanceRole = new Role(this, 'MM-Bot-InstanceRole', {
            assumedBy: new ServicePrincipal('ec2.amazonaws.com'),
        });
        instanceRole.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonEC2ContainerServiceforEC2Role'));
        const launchTemplate = new LaunchTemplate(this, 'MM-Bot-LaunchTemplate', {
            instanceType: InstanceType.of(InstanceClass.T4G, InstanceSize.NANO),
            machineImage: MachineImage.latestAmazonLinux2023({
                cpuType: AmazonLinuxCpuType.ARM_64,
            }),
            securityGroup: securityGroup,
            role: instanceRole,
            blockDevices: [],
        });
        const autoscalingGroup = new AutoScalingGroup(this, 'MM-Bot-AutoScalingGroup', {
            desiredCapacity: 1,
            vpcSubnets: { subnetType: SubnetType.PUBLIC },
            vpc: vpc,
            launchTemplate: launchTemplate,
        });
        const capacityProvider = new AsgCapacityProvider(this, 'MM-Bot-AsgCapProvider', {
            autoScalingGroup: autoscalingGroup,
        });
        cluster.addAsgCapacityProvider(capacityProvider);
  
        /**
         * Task Definition
         */

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
        props.matchQueuesTable.grantFullAccess(taskRole);

        // Define the EC2 task with container details
        const ec2TaskDefinition = new Ec2TaskDefinition(this, 'MM-Bot-Task', {
            taskRole: taskRole,
        });

        /**
         * Container
         */
        const container = ec2TaskDefinition.addContainer('MM-Bot-Container', {
            image: ContainerImage.fromDockerImageAsset(dockerImageAsset),
            logging: new AwsLogDriver({
                streamPrefix: 'MMBot',
            }),
            environment: {
                SECRETS_BUCKET: props.secretsBucket.bucketName,
                PLAYER_PROFILES_TABLE: props.playerProfilesTable.tableName,
                MATCH_RESULTS_TABLE: props.matchResultsTable.tableName,
                MATCH_QUEUES_TABLE: props.matchQueuesTable.tableName,
            },
            memoryReservationMiB: 256,
            memoryLimitMiB: 512,
            cpu: 256,
        });
    
        container.addPortMappings({
            containerPort: 80, // Match this with the port exposed in Dockerfile
            hostPort: 8080,
            protocol: Protocol.TCP,
        });
    
        /**
         * EC2 Service
         */
        const ec2Service = new Ec2Service(this, 'MM-Bot-Service', {
            cluster, 
            taskDefinition: ec2TaskDefinition,
        });
    }
}