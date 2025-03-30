from openai import OpenAI
import re
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {"origins": "*"},
    r"/": {"origins": "*"}
})

@app.route('/api/swap')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Swap 接口测试页</h1>
        <input id="input" placeholder="输入兑换请求，如：我要把5个ETH换成BNB">
        <button onclick="sendRequest()">测试</button>
        <div id="result"></div>
        
        <script>
            async function sendRequest() {
                const input = document.getElementById('input').value;
                const resultDiv = document.getElementById('result');
                
                try {
                    const response = await fetch('/api/swap', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ text: input })
                    });
                    
                    const data = await response.json();
                    resultDiv.innerHTML = JSON.stringify(data, null, 2);
                } catch (error) {
                    resultDiv.innerHTML = '请求失败: ' + error.message;
                }
            }
        </script>
    </body>
    </html>
    """

class SwapIntentParser:
    """代币交换意图解析器"""
    
    @staticmethod
    def parse_input(text: str) -> dict:
        """
        解析用户输入，提取代币交换参数
        返回结构：{
            "from_token": str,
            "from_amount": float,
            "to_token": str,
            "raw_text": str
        }
        """
        # 预处理文本
        cleaned_text = text.replace("，", ",").replace(" ", "").lower()
        
        # 使用正则表达式匹配模式
        patterns = [
            r"(\d+\.?\d*)[个|枚]?([a-z]+)换成([a-z]+)",      # 格式：X个A换成B
            r"把(\d+\.?\d*)([a-z]+)转化为([a-z]+)",         # 格式：把XA转化为B
            r"将([a-z]+)中的(\d+\.?\d*)兑换为([a-z]+)",     # 格式：将A中的X兑换为B
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    return {
                        "from_amount": float(groups[0]),
                        "from_token": groups[1].upper(),
                        "to_token": groups[2].upper(),
                        "raw_text": text
                    }
        
        # 如果未匹配到模式，返回空值
        return None

class Web3ChatInterface:
    def __init__(self, api_key=None):
        self.client = OpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1"
        )
        self.parser = SwapIntentParser()
    
    def process_request(self, user_input: str) -> dict:
        """处理用户请求的完整流程"""
        try:
            # 第一步：解析用户输入
            parsed = self.parser.parse_input(user_input)
            
            # 第二步：调用AI生成补充信息
            ai_response = self._get_ai_response(user_input)
            
            return {
                "status": "success",
                "parsed_parameters": parsed or {},
                "ai_analysis": ai_response,
                "transaction_payload": self._build_transaction_payload(parsed)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "error_type": type(e).__name__
            }
    
    def _get_ai_response(self, text: str) -> str:
        """获取AI生成的补充分析"""
        messages = [{
            "role": "system",
            "content": "你是一个专业的DeFi助手，请用JSON格式补充以下信息："
                      "1. 推荐交易平台（dex） 2. 预估滑点 3. 最优路径建议"
        }, {
            "role": "user",
            "content": text
        }]
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3
        )
        return response.choices[0].message.content
    
    def _build_transaction_payload(self, parsed: dict) -> dict:
        """构建交易payload（示例）"""
        if not parsed:
            return {}
            
        return {
            "swap": {
                "from": parsed["from_token"],
                "amount": parsed["from_amount"],
                "to": parsed["to_token"]
            },
            "default_dex": "Uniswap V3",
            "allowance_check": True
        }

# API端点配置
@app.route('/api/swap', methods=['POST'])
def handle_swap_request():
    data = request.json
    if not data or 'text' not in data:
        return jsonify({"error": "Missing text parameter"}), 400
    
    interface = Web3ChatInterface()
    result = interface.process_request(data['text'])
    
    # 添加CORS头
    response = jsonify(result)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

if __name__ == "__main__":
    # 启动服务：flask run --port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)

# 测试用例
test_cases = [
    "我想要把5个ETH换成BNB",
    "请帮我把3.2枚USDC转化为DAI",
    "将MATIC中的10兑换成APE"
]