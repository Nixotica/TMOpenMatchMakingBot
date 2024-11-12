import { BlockDeviceVolume, EbsDeviceVolumeType } from "aws-cdk-lib/aws-autoscaling";
import { Table } from "aws-cdk-lib/aws-dynamodb";
import { Instance, InstanceClass, InstanceSize, InstanceType, MachineImage, Peer, Port, RouterType, SecurityGroup, Subnet, SubnetType, Vpc } from "aws-cdk-lib/aws-ec2";
import { BlockDevice } from "aws-cdk-lib/aws-autoscaling";
import { DockerImageAsset } from "aws-cdk-lib/aws-ecr-assets";
import { AwsLogDriver, Cluster, ContainerImage, DeploymentControllerType, Ec2Service, Ec2TaskDefinition, PlacementConstraint, Protocol } from "aws-cdk-lib/aws-ecs";
import { Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { Bucket } from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";
import path = require("path");
import { Duration, Stack, StackProps } from "aws-cdk-lib";

export interface BotServiceStackProps extends StackProps {
    /** The stage of this stack (dev, prod). */
    stage: string,

    /** A bucket containing secrets used by the bot during runtime. */
    secretsBucket: Bucket,

    /** A table containing player specific information. */
    playerProfilesTable: Table,

    /** A table containing player elos by leaderboard. */
    playerElosTable: Table,

    /** A table containing match results. */
    matchResultsTable: Table,

    /** A table containing available matchmaking queues. */
    matchQueuesTable: Table,

    /** A table containing leaderboards. */
    leaderboardsTable: Table,

    /** A table containing ranks for the global leaderboard. */
    ranksTable: Table,

    /** A table containing ranks associated to leaderboards by ID. */
    leaderboardRanksTable: Table,
}

/**
 * A construct for deploying a container to host the bot. 
 */
export class BotServiceStack extends Stack {
    constructor(scope: Construct, id: string, props: BotServiceStackProps) {
        super(scope, id, props);

        /**
         * VPC 
         */
        const vpc = new Vpc(this, 'MM-Bot-VPC', {
            maxAzs: 1,
        });

        /**
         * Security Group
         */
        const ecsSecurityGroup = new SecurityGroup(this, 'EcsSecurityGroup', {
            vpc,
            description: 'Allow inbound HTTP/HTTPS traffic to ECS instances',
            allowAllOutbound: true,
        });

        // Allow inbound traffic on port 80 (HTTP) from any IP
        ecsSecurityGroup.addIngressRule(
            Peer.anyIpv4(), // Accepts traffic from any IP
            Port.tcp(80),   // HTTP port
            'Allow inbound HTTP traffic'
        );

        // Allow inbound traffic on port 8080 (HTTP) from any IP
        ecsSecurityGroup.addIngressRule(
            Peer.anyIpv4(), // Accepts traffic from any IP
            Port.tcp(8080),   // HTTP port
            'Allow inbound HTTP traffic'
        );

        // (Optional) Allow HTTPS traffic if your app needs it
        ecsSecurityGroup.addIngressRule(
            Peer.anyIpv4(), // Accepts traffic from any IP
            Port.tcp(443),  // HTTPS port
            'Allow inbound HTTPS traffic'
        );

        /**
         * ECS Cluster
         */
        const cluster = new Cluster(this, 'MM-Bot-Cluster', {
            vpc,
        });
        const rootVolume: BlockDevice = {
            deviceName: '/dev/xvda',
            volume: BlockDeviceVolume.ebs(
                30,
                {
                    volumeType: EbsDeviceVolumeType.STANDARD,
                }
            )
        };
        const autoScalingGroup = cluster.addCapacity('MM-Bot-DefaultAutoScalingGroup', {
            instanceType: InstanceType.of(InstanceClass.BURSTABLE3_AMD, InstanceSize.NANO), 
            blockDevices: [rootVolume],
        });
        autoScalingGroup.addSecurityGroup(ecsSecurityGroup);

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
        props.playerElosTable.grantFullAccess(taskRole);
        props.matchResultsTable.grantFullAccess(taskRole);
        props.matchQueuesTable.grantFullAccess(taskRole);
        props.leaderboardsTable.grantFullAccess(taskRole);
        props.ranksTable.grantFullAccess(taskRole);
        props.leaderboardRanksTable.grantFullAccess(taskRole);

        // Define the EC2 task with container details
        const ec2TaskDefinition = new Ec2TaskDefinition(this, 'MM-Bot-Task', {
            taskRole: taskRole,
        });

        /**
         * Container
         */
        const container = ec2TaskDefinition.addContainer('MM-Bot-Container', {
            image: ContainerImage.fromDockerImageAsset(dockerImageAsset),
            logging: AwsLogDriver.awsLogs({ streamPrefix: 'mm-bot' }),
            environment: {
                SECRETS_BUCKET: props.secretsBucket.bucketName,
                PLAYER_PROFILES_TABLE: props.playerProfilesTable.tableName,
                PLAYER_ELOS_TABLE: props.playerElosTable.tableName,
                MATCH_RESULTS_TABLE: props.matchResultsTable.tableName,
                MATCH_QUEUES_TABLE: props.matchQueuesTable.tableName,
                LEADERBOARDS_TABLE: props.leaderboardsTable.tableName,
                RANKS_TABLE: props.ranksTable.tableName,
                LEADERBOARD_RANKS_TABLE: props.leaderboardRanksTable.tableName,
                AWS_REGION: 'us-west-2',
                AWS_DEFAULT_REGION: 'us-west-2',
            },
            memoryReservationMiB: 128, // Soft limit
            memoryLimitMiB: 256, // Hard limit
            healthCheck: {
                command: ['CMD-SHELL', 'curl -f http://localhost:8080/health || exit 1']
            }
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
            desiredCount: 1,
            deploymentController: {
                type: DeploymentControllerType.ECS,
            },
            placementConstraints: [
                PlacementConstraint.distinctInstances(),
            ],
            healthCheckGracePeriod: Duration.seconds(120),
        });
    }
}