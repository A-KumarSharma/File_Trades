from flask import Flask, render_template_string, request, jsonify # type: ignore
import csv
from collections import defaultdict
from datetime import datetime
import os
import uuid

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# HTML Template as a string
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trade P&L Calculator</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .profit { color: #10B981; }
        .loss { color: #EF4444; }
        .highlight { background-color: rgba(59, 130, 246, 0.1); }
    </style>
</head>
<body class="bg-gray-50">
    <div class="container mx-auto px-4 py-8">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold text-indigo-700">Trade Profit & Loss Calculator</h1>
            <p class="text-gray-600 mt-2">Upload your trades CSV file to analyze your performance</p>
        </div>

        <div class="bg-white rounded-lg shadow p-6 mb-8">
            <div class="flex flex-col md:flex-row gap-4">
                <div class="flex-grow">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Select CSV File</label>
                    <input type="file" id="fileInput" accept=".csv" class="block w-full text-sm text-gray-500
                        file:mr-4 file:py-2 file:px-4
                        file:rounded-md file:border-0
                        file:text-sm file:font-semibold
                        file:bg-indigo-50 file:text-indigo-700
                        hover:file:bg-indigo-100">
                </div>
                <div class="mt-6 md:mt-0">
                    <button onclick="analyzeTrades()" class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition">
                        Analyze Trades
                    </button>
                </div>
            </div>
        </div>

        <div id="loading" class="hidden text-center py-8">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-600"></div>
            <p class="mt-2 text-gray-600">Processing your trades...</p>
        </div>

        <div id="results" class="hidden">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Total P&L</h3>
                    <p id="totalPnl" class="text-2xl font-bold"></p>
                    <p id="tradeCount" class="text-sm text-gray-500"></p>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Win Rate</h3>
                    <p id="winRate" class="text-2xl font-bold"></p>
                    <p id="winLoss" class="text-sm text-gray-500"></p>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Performance</h3>
                    <p id="avgPnl" class="text-sm mb-1"></p>
                    <p id="maxMin" class="text-sm"></p>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow p-6 mb-8">
                <h2 class="text-xl font-semibold mb-4">Performance Distribution</h2>
                <canvas id="performanceChart" height="200"></canvas>
            </div>

            <div class="bg-white rounded-lg shadow overflow-hidden mb-8">
                <div class="px-6 py-4 border-b border-gray-200">
                    <h2 class="text-xl font-semibold">Trade Details</h2>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Dates</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">P&L</th>
                            </tr>
                        </thead>
                        <tbody id="tradeTableBody" class="bg-white divide-y divide-gray-200">
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="error" class="hidden bg-red-50 border-l-4 border-red-400 p-4 mb-8">
            <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                    </svg>
                </div>
                <div class="ml-3">
                    <p id="errorMessage" class="text-sm text-red-700"></p>
                </div>
            </div>
        </div>
    </div>

    <script>
        function analyzeTrades() {
            const fileInput = document.getElementById('fileInput');
            const loading = document.getElementById('loading');
            const results = document.getElementById('results');
            const error = document.getElementById('error');
            
            if (!fileInput.files.length) {
                showError('Please select a CSV file first');
                return;
            }
            
            loading.classList.remove('hidden');
            results.classList.add('hidden');
            error.classList.add('hidden');
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    showError(data.error || 'Error processing file');
                    return;
                }
                displayResults(data.summary, data.trades);
                loading.classList.add('hidden');
                results.classList.remove('hidden');
            })
            .catch(err => {
                showError('An error occurred while processing your file');
                console.error(err);
            })
            .finally(() => {
                loading.classList.add('hidden');
            });
        }

        function showError(message) {
            const error = document.getElementById('error');
            const errorMessage = document.getElementById('errorMessage');
            
            errorMessage.textContent = message;
            error.classList.remove('hidden');
        }

        function displayResults(summary, trades) {
            document.getElementById('totalPnl').textContent = formatCurrency(summary.total_pnl);
            document.getElementById('totalPnl').className = `text-2xl font-bold ${summary.total_pnl >= 0 ? 'profit' : 'loss'}`;
            
            document.getElementById('tradeCount').textContent = `${summary.total_trades} trades across ${summary.symbol_count} symbols`;
            
            document.getElementById('winRate').textContent = `${summary.win_rate.toFixed(1)}%`;
            document.getElementById('winLoss').textContent = `${summary.winning_trades} wins / ${summary.losing_trades} losses`;
            
            document.getElementById('avgPnl').textContent = `Avg P&L: ${formatCurrency(summary.avg_pnl)}`;
            document.getElementById('avgPnl').className = `text-sm mb-1 ${summary.avg_pnl >= 0 ? 'profit' : 'loss'}`;
            
            document.getElementById('maxMin').textContent = `Max Win: ${formatCurrency(summary.max_win)} | Max Loss: ${formatCurrency(summary.max_loss)}`;
            
            const tableBody = document.getElementById('tradeTableBody');
            tableBody.innerHTML = '';
            
            trades.forEach(trade => {
                const row = document.createElement('tr');
                row.className = 'hover:highlight';
                
                row.innerHTML = `
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${trade.symbol}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${trade.open_date} to ${trade.close_date}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${trade.open_action} → ${trade.close_action}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${trade.quantity}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm ${trade.pnl >= 0 ? 'profit' : 'loss'}">
                        ${formatCurrency(trade.pnl)}
                    </td>
                `;
                
                tableBody.appendChild(row);
            });
            
            createPerformanceChart(trades);
        }

        function formatCurrency(value) {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).format(value);
        }

        function createPerformanceChart(trades) {
            const ctx = document.getElementById('performanceChart').getContext('2d');
            
            const symbolData = {};
            trades.forEach(trade => {
                if (!symbolData[trade.symbol]) {
                    symbolData[trade.symbol] = 0;
                }
                symbolData[trade.symbol] += trade.pnl;
            });
            
            const sortedSymbols = Object.keys(symbolData).sort((a, b) => symbolData[b] - symbolData[a]);
            
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: sortedSymbols,
                    datasets: [{
                        label: 'Total P&L by Symbol',
                        data: sortedSymbols.map(symbol => symbolData[symbol]),
                        backgroundColor: sortedSymbols.map(symbol => 
                            symbolData[symbol] >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)'
                        ),
                        borderColor: sortedSymbols.map(symbol => 
                            symbolData[symbol] >= 0 ? 'rgba(16, 185, 129, 1)' : 'rgba(239, 68, 68, 1)'
                        ),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    </script>
</body>
</html>
"""

# Business Logic Functions
def parse_csv(file_path):
    trades = []
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            row['Quantity'] = float(row['Quantity']) if row['Quantity'] else 0.0
            row['Price'] = float(row['Price']) if row['Price'] else 0.0
            row['Fees'] = float(row['Fees']) if row['Fees'] else 0.0
            row['Amount'] = float(row['Amount']) if row['Amount'] else 0.0
            trades.append(row)
    return trades

def match_trades(trades):
    symbol_groups = defaultdict(list)
    for trade in trades:
        symbol_groups[trade['Symbol']].append(trade)
    
    matched_trades = []
    for symbol, symbol_trades in symbol_groups.items():
        symbol_trades.sort(key=lambda x: datetime.strptime(x['Date'], '%m/%d/%Y'))
        
        opening_trades = []
        closing_trades = []
        
        for trade in symbol_trades:
            action = trade['Action']
            if action in ['Buy', 'Buy to Open']:
                opening_trades.append(trade)
            elif action in ['Sell', 'Sell to Open']:
                opening_trades.append(trade)
            elif action in ['Sell to Close', 'Buy to Close', 'Expired']:
                closing_trades.append(trade)
        
        for open_trade in opening_trades:
            matching_close = None
            for i, close_trade in enumerate(closing_trades):
                if (open_trade['Action'] in ['Buy', 'Buy to Open'] and 
                    close_trade['Action'] in ['Sell to Close', 'Expired']):
                    matching_close = close_trade
                    del closing_trades[i]
                    break
                elif (open_trade['Action'] in ['Sell', 'Sell to Open'] and 
                      close_trade['Action'] in ['Buy to Close', 'Expired']):
                    matching_close = close_trade
                    del closing_trades[i]
                    break
            
            if matching_close:
                close_amount = 0.0 if matching_close['Action'] == 'Expired' else matching_close['Amount']
                pnl = close_amount - open_trade['Amount']
                matched_trades.append({
                    'symbol': symbol,
                    'open_date': open_trade['Date'],
                    'close_date': matching_close['Date'],
                    'open_action': open_trade['Action'],
                    'close_action': matching_close['Action'],
                    'quantity': open_trade['Quantity'],
                    'open_amount': open_trade['Amount'],
                    'close_amount': close_amount,
                    'pnl': pnl,
                    'description': open_trade['Description']
                })
    
    return matched_trades

def calculate_summary(matched_trades):
    summary = {
        'total_trades': len(matched_trades),
        'winning_trades': 0,
        'losing_trades': 0,
        'total_pnl': 0.0,
        'avg_pnl': 0.0,
        'max_win': 0.0,
        'max_loss': 0.0,
        'symbols': set()  # Keep this as a set for internal processing
    }
    
    if not matched_trades:
        return summary
    
    for trade in matched_trades:
        summary['symbols'].add(trade['symbol'])
        summary['total_pnl'] += trade['pnl']
        if trade['pnl'] >= 0:
            summary['winning_trades'] += 1
            summary['max_win'] = max(summary['max_win'], trade['pnl'])
        else:
            summary['losing_trades'] += 1
            summary['max_loss'] = min(summary['max_loss'], trade['pnl'])
    
    summary['avg_pnl'] = summary['total_pnl'] / summary['total_trades']
    summary['win_rate'] = (summary['winning_trades'] / summary['total_trades']) * 100
    summary['symbol_count'] = len(summary['symbols'])
    
    # Convert the set to a list for JSON serialization
    summary['symbols'] = list(summary['symbols'])
    
    return summary

# Routes
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.csv'):
        # Generate unique filename to prevent conflicts
        filename = f"{uuid.uuid4().hex}.csv"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            trades = parse_csv(filepath)
            matched_trades = match_trades(trades)
            summary = calculate_summary(matched_trades)
            
            matched_trades_sorted = sorted(matched_trades, key=lambda x: x['pnl'], reverse=True)
            
            return jsonify({
                'success': True,
                'summary': summary,
                'trades': matched_trades_sorted[:100]  # Limit to 100 trades for display
            })
        except Exception as e:
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
        finally:
            # Clean up - remove the uploaded file after processing
            if os.path.exists(filepath):
                os.remove(filepath)
    else:
        return jsonify({'error': 'Invalid file type. Please upload a CSV file'}), 400

if __name__ == '__main__':
    app.run(debug=True)
