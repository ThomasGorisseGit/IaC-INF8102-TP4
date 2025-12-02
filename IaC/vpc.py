# Fichier : vpc.py (FINALEMENT CORRIGÉ - Q1, Q3.1, Q3.2)

import os
from troposphere import Template, ec2, Ref, Join, GetAtt, Select, GetAZs, iam, Tags, cloudwatch 
from awacs.aws import Allow, Statement, Principal, Policy
from awacs.sts import AssumeRole
from awacs.s3 import PutObject, PutObjectAcl, GetBucketAcl 

# --- PARAMÈTRES DE BASE ---
VPC_CIDR = "10.0.0.0/16"
PUBLIC_SUBNET_AZ1_CIDR = "10.0.1.0/24"
PUBLIC_SUBNET_AZ2_CIDR = "10.0.2.0/24"
PRIVATE_SUBNET_AZ1_CIDR = "10.0.10.0/24"
PRIVATE_SUBNET_AZ2_CIDR = "10.0.20.0/24"
PROJECT_NAME = "polystudentlab"
VPC_NAME = "polystudent-vpc1"
FLOW_LOG_BUCKET_NAME = "polystudens3" 
AMI_ID = "ami-053b01d51de5a4358" # Remplacer par une AMI Linux valide
INSTANCE_TYPE = "t2.micro" 

t = Template()
t.set_description("TP4 INF8102 - VPC, Subnets, Flow Logs, EC2 Instances, and CloudWatch Alarm")

# --- 1. Rôle IAM pour VPC Flow Logs (Q3.1) ---
flowLogRole = t.add_resource(iam.Role(
    "FlowLogRole",
    AssumeRolePolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow, Principal=Principal("Service", "vpc-flow-logs.amazonaws.com"), Action=[AssumeRole]
            )
        ]
    ),
    Policies=[
        iam.Policy(
            PolicyName="FlowLogPolicy",
            PolicyDocument=Policy(
                Statement=[
                    Statement(
                        Effect=Allow, Action=[PutObject, PutObjectAcl, GetBucketAcl], 
                        Resource=Join("", ["arn:aws:s3:::", FLOW_LOG_BUCKET_NAME, "/*"])
                    ),
                    Statement(
                        Effect=Allow, Action=[GetBucketAcl],
                        Resource=Join("", ["arn:aws:s3:::", FLOW_LOG_BUCKET_NAME])
                    )
                ]
            )
        )
    ],
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "flowlog-role"])})
))

# --- 2. IAM Role et Instance Profile pour EC2 (Q3.2) ---
labRole = t.add_resource(iam.Role(
    "LabRole",
    AssumeRolePolicyDocument=Policy(
        Statement=[Statement(Effect=Allow, Principal=Principal("Service", "ec2.amazonaws.com"), Action=[AssumeRole])]
    ),
    ManagedPolicyArns=["arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"], 
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "lab-role"])})
))

labInstanceProfile = t.add_resource(iam.InstanceProfile("LabInstanceProfile", Roles=[Ref(labRole)]))

# --- 3. VPC (Q1) ---
vpc = t.add_resource(ec2.VPC(
    "VPC", CidrBlock=VPC_CIDR, EnableDnsSupport="true", EnableDnsHostnames="true", Tags=Tags({"Name": VPC_NAME})
))

AZ1 = Select(0, GetAZs(Ref("AWS::Region")))
AZ2 = Select(1, GetAZs(Ref("AWS::Region")))

# Subnets Publics (Q1)
publicSubnetAZ1 = t.add_resource(ec2.Subnet(
    "PublicSubnetAZ1", VpcId=Ref(vpc), CidrBlock=PUBLIC_SUBNET_AZ1_CIDR, AvailabilityZone=AZ1,
    MapPublicIpOnLaunch=True, Tags=Tags({"Name": Join("-", [PROJECT_NAME, "public-az1"])})
))
publicSubnetAZ2 = t.add_resource(ec2.Subnet(
    "PublicSubnetAZ2", VpcId=Ref(vpc), CidrBlock=PUBLIC_SUBNET_AZ2_CIDR, AvailabilityZone=AZ2,
    MapPublicIpOnLaunch=True, Tags=Tags({"Name": Join("-", [PROJECT_NAME, "public-az2"])})
))

# Subnets Privés (Q1)
privateSubnetAZ1 = t.add_resource(ec2.Subnet(
    "PrivateSubnetAZ1", VpcId=Ref(vpc), CidrBlock=PRIVATE_SUBNET_AZ1_CIDR, AvailabilityZone=AZ1,
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "private-az1"])})
))
privateSubnetAZ2 = t.add_resource(ec2.Subnet(
    "PrivateSubnetAZ2", VpcId=Ref(vpc), CidrBlock=PRIVATE_SUBNET_AZ2_CIDR, AvailabilityZone=AZ2,
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "private-az2"])})
))

# --- 4. IGW, NAT, Routes (Q1) ---
internetGateway = t.add_resource(ec2.InternetGateway(
    "InternetGateway", Tags=Tags({"Name": Join("-", [PROJECT_NAME, "igw"])})
))
t.add_resource(ec2.VPCGatewayAttachment("AttachGateway", VpcId=Ref(vpc), InternetGatewayId=Ref(internetGateway)))
natGatewayEIP = t.add_resource(ec2.EIP("NatGatewayEIP", Domain="vpc", Tags=Tags({"Name": Join("-", [PROJECT_NAME, "nat-eip"])})))
natGateway = t.add_resource(ec2.NatGateway(
    "NatGateway", AllocationId=GetAtt(natGatewayEIP, "AllocationId"), SubnetId=Ref(publicSubnetAZ1), 
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "nat-az1"])})
))
publicRouteTable = t.add_resource(ec2.RouteTable("PublicRouteTable", VpcId=Ref(vpc), Tags=Tags({"Name": Join("-", [PROJECT_NAME, "public-rt"])})))
t.add_resource(ec2.Route("PublicRoute", RouteTableId=Ref(publicRouteTable), DestinationCidrBlock="0.0.0.0/0", GatewayId=Ref(internetGateway), DependsOn="AttachGateway"))
privateRouteTable = t.add_resource(ec2.RouteTable("PrivateRouteTable", VpcId=Ref(vpc), Tags=Tags({"Name": Join("-", [PROJECT_NAME, "private-rt"])})))
t.add_resource(ec2.Route("PrivateRoute", RouteTableId=Ref(privateRouteTable), DestinationCidrBlock="0.0.0.0/0", NatGatewayId=Ref(natGateway)))
t.add_resource(ec2.SubnetRouteTableAssociation("PublicSubnetRouteTableAssociationAZ1", SubnetId=Ref(publicSubnetAZ1), RouteTableId=Ref(publicRouteTable)))
t.add_resource(ec2.SubnetRouteTableAssociation("PublicSubnetRouteTableAssociationAZ2", SubnetId=Ref(publicSubnetAZ2), RouteTableId=Ref(publicRouteTable)))
t.add_resource(ec2.SubnetRouteTableAssociation("PrivateSubnetRouteTableAssociationAZ1", SubnetId=Ref(privateSubnetAZ1), RouteTableId=Ref(privateRouteTable)))
t.add_resource(ec2.SubnetRouteTableAssociation("PrivateSubnetRouteTableAssociationAZ2", SubnetId=Ref(privateSubnetAZ2), RouteTableId=Ref(privateRouteTable)))


# --- 5. Security Group pour les Instances EC2 (Q3.2) ---
labSecurityGroup = t.add_resource(ec2.SecurityGroup(
    "LabSecurityGroup",
    GroupDescription="Allow SSH access and all internal traffic",
    VpcId=Ref(vpc),
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(IpProtocol="tcp", FromPort="22", ToPort="22", CidrIp="0.0.0.0/0"),
        ec2.SecurityGroupRule(IpProtocol="-1", SourceSecurityGroupId=GetAtt("LabSecurityGroup", "GroupId"))
    ],
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "lab-sg"])})
))

# --- 6. Instances EC2 (Q3.2) ---
def create_ec2_instance(name, subnet_ref, t):
    return t.add_resource(ec2.Instance(
        name,
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        SubnetId=Ref(subnet_ref),
        SecurityGroupIds=[Ref(labSecurityGroup)],
        IamInstanceProfile=Ref(labInstanceProfile),
        Tags=Tags({"Name": Join("-", [PROJECT_NAME, name])})
    ))

publicInstanceAZ1 = create_ec2_instance("PublicInstanceAZ1", publicSubnetAZ1, t)
publicInstanceAZ2 = create_ec2_instance("PublicInstanceAZ2", publicSubnetAZ2, t)
privateInstanceAZ1 = create_ec2_instance("PrivateInstanceAZ1", privateSubnetAZ1, t)
privateInstanceAZ2 = create_ec2_instance("PrivateInstanceAZ2", privateSubnetAZ2, t)


# --- 7. CloudWatch Alarm (NetworkPacketsIn) (Q3.2) ---
t.add_resource(cloudwatch.Alarm(
    "TrafficAlarm",
    AlarmDescription="Alarme si le trafic d'entrée dépasse 1000 paquets/sec en moyenne",
    EvaluationPeriods="5", 
    Threshold="1000",
    ComparisonOperator="GreaterThanThreshold",
    
    # CORRECTION: Suppression des propriétés simples (Statistic, MetricName, etc.)
    Metrics=[
        cloudwatch.MetricDataQuery(
            Id="m1",
            MetricStat=cloudwatch.MetricStat(
                Metric=cloudwatch.Metric(
                    Namespace="AWS/EC2",
                    MetricName="NetworkPacketsIn",
                    # Ciblage des quatre instances par leurs IDs
                    Dimensions=[
                        cloudwatch.MetricDimension(Name="InstanceId", Value=Ref(publicInstanceAZ1)),
                        cloudwatch.MetricDimension(Name="InstanceId", Value=Ref(publicInstanceAZ2)),
                        cloudwatch.MetricDimension(Name="InstanceId", Value=Ref(privateInstanceAZ1)),
                        cloudwatch.MetricDimension(Name="InstanceId", Value=Ref(privateInstanceAZ2))
                    ]
                ),
                Period="60",
                Stat="Average"
            ),
            ReturnData="true",
        )
    ],
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "traffic-alarm"])})
))


# --- 8. VPC Flow Log (Q3.1) ---
flowLog = t.add_resource(ec2.FlowLog(
    "VPCFlowLog",
    DeliverLogsPermissionArn=GetAtt(flowLogRole, "Arn"),
    ResourceId=Ref(vpc),
    ResourceType="VPC",
    TrafficType="REJECT", 
    LogDestinationType="s3",
    LogDestination=Join("", ["arn:aws:s3:::", FLOW_LOG_BUCKET_NAME]),
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "vpc-flow-log"])})
))

# Imprimer le template CloudFormation généré en YAML
print(t.to_yaml())