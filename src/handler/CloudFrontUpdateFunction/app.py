import json
import boto3
import os
import time
          
def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")
    print(f"Context: {context}")
              
    # 環境変数の取得
    distribution_id = os.environ['DISTRIBUTION_ID']
    project_name = os.environ['PROJECT_NAME']
    environment = os.environ['ENVIRONMENT']
              
    # クライアントの初期化
    cloudfront = boto3.client('cloudfront')
    ec2 = boto3.client('ec2')
              
    try:
        # イベントからインスタンスIDを取得
        instance_id = event['detail']['instance-id']
        print(f"Instance state changed: {instance_id}")
        
        # インスタンスの詳細情報を取得
        instance_response = ec2.describe_instances(InstanceIds=[instance_id])
        if not instance_response['Reservations']:
            raise Exception(f"Instance {instance_id} not found")
        
        instance = instance_response['Reservations'][0]['Instances'][0]
        
        # インスタンスが実行中でない場合はスキップ
        if instance['State']['Name'] != 'running':
            print(f"Instance {instance_id} is not running (state: {instance['State']['Name']})")
            return {
                'statusCode': 200,
                'body': json.dumps(f'Instance {instance_id} is not running')
            }
        
        # インスタンスのタグを確認
        instance_tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        if (instance_tags.get('Project') != project_name or 
            instance_tags.get('Environment') != environment):
            print(f"Instance {instance_id} does not match project/environment criteria")
            return {
                'statusCode': 200,
                'body': json.dumps('Instance does not match criteria')
            }
        
        new_domain_name = instance['PublicDnsName']
        print(f"Instance {instance_id} domain name: {new_domain_name}")
        
        # CloudFrontディストリビューションの現在の設定を取得
        dist_response = cloudfront.get_distribution(Id=distribution_id)
        distribution_config = dist_response['Distribution']['DistributionConfig']
        etag = dist_response['ETag']
        
        # OriginのDomainNameを更新
        origin_id = f"{project_name}-{environment}-origin"  # テンプレート内で指定したIDと同じ
        origin_updated = False
        
        for origin in distribution_config['Origins']['Items']:
            if origin['Id'] == origin_id:
                old_domain_name = origin['DomainName']
                if old_domain_name != new_domain_name:
                    origin['DomainName'] = new_domain_name
                    origin_updated = True
                    print(f"Updating origin {origin_id} from {old_domain_name} to {new_domain_name}")
                else:
                    print(f"Origin {origin_id} already has correct domain name: {new_domain_name}")
                break
        
        if not origin_updated:
            return {
                'statusCode': 200,
                'body': json.dumps('No update needed')
            }
        
        # CloudFrontディストリビューションを更新
        cloudfront.update_distribution(
            Id=distribution_id,
            DistributionConfig=distribution_config,
            IfMatch=etag
        )
        
        print(f"CloudFront distribution update initiated")
        
        # 更新の完了を待機（最大5分）
        max_wait_time = 300  # 5分
        wait_interval = 30   # 30秒間隔
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            time.sleep(wait_interval)
            elapsed_time += wait_interval
            
            # ディストリビューションの状態を確認
            status_response = cloudfront.get_distribution(Id=distribution_id)
            status = status_response['Distribution']['Status']
            
            print(f"Distribution status: {status}")
            
            if status == 'Deployed':
                print("CloudFront distribution update completed")
                break
            elif status == 'Failed':
                raise Exception("CloudFront distribution update failed")
        
        if elapsed_time >= max_wait_time:
            print("Warning: CloudFront distribution update may still be in progress")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'CloudFront distribution updated successfully',
                'instance_id': instance_id,
                'new_domain': new_domain_name
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }