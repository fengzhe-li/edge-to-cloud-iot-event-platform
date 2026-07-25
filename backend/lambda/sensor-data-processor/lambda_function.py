import json
import os
import boto3

def lambda_handler(event, context):
    # 1. 打印原始输入日志 (非常重要，方便在 CloudWatch 调试)
    print(f"Received event: {json.dumps(event)}")
    
    # 2. 灵活解析传感器 ID 和 状态
    # 兼容两种写法：sensor_id (pgAdmin风格) 和 sensorId (常用风格)
    sid = event.get('sensor_id') or event.get('sensorId') or "Unknown"
    sstatus = str(event.get('state', '')).lower()
    
    # 3. 数据库入库逻辑 (包含异常保护)
    try:
        import psycopg2
        import os
        # 建立连接
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD')
        )
        cur = conn.cursor()
        # 调用存储过程入库
        cur.execute("SELECT insert_sensor_json(%s)", (json.dumps(event),))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Successfully recorded data for Sensor {sid} in Aurora.")
    except ImportError:
        print("Warning: psycopg2 layer missing. Database insert skipped.")
    except Exception as e:
        print(f"Database Error: {str(e)}")

    # 4. 【核心自动化判断】
    if 'wet' in sstatus:
        print(f"DETECTED WET STATE for sensor {sid}. Triggering AlertNotificationServiceauto...")
        try:
            lambda_client = boto3.client('lambda')
            
            # 构造发送给邮件函数的内容
            email_payload = {
                "to": [os.environ.get("ALERT_RECIPIENT", "operations@example.com")],
                "subject": f"⚠️ URGENT: Leak Detected at Sensor {sid}",
                "message": f"Critical notification: Sensor {sid} has entered a WET state. Please check your system."
            }
            
            # 【关键修改】这里必须对应你的新函数名
            lambda_client.invoke(
                FunctionName='AlertNotificationServiceauto', 
                InvocationType='Event', # 异步调用，不阻塞当前进程
                Payload=json.dumps(email_payload)
            )
            print("Successfully triggered the alert service.")
        except Exception as e:
            print(f"Failed to call alert function: {str(e)}")
    else:
        print(f"Sensor {sid} is currently DRY. No alert needed.")
    
    return {"status": "Success", "sensorId": sid}