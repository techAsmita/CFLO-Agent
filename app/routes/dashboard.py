import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from data.database import get_connection
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM borrowers ORDER BY dpd DESC")
    borrowers = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM ptp_log ORDER BY captured_at DESC LIMIT 20")
    ptps = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM call_log ORDER BY started_at DESC LIMIT 20")
    calls = [dict(row) for row in cursor.fetchall()]

    conn.close()

    segment_colors = {
        "S1": "#ef4444", "S2": "#f97316",
        "S3": "#eab308", "S4": "#3b82f6", "S5": "#22c55e"
    }

    borrower_rows = ""
    for b in borrowers:
        color = segment_colors.get(b["risk_segment"], "#888")
        borrower_rows += f"""
        <tr>
            <td>{b['name']}</td>
            <td>{b['loan_account']}</td>
            <td>Rs {b['outstanding_balance']:,.0f}</td>
            <td>Rs {b['emi_amount']:,.0f}</td>
            <td>{b['emi_due_date']}</td>
            <td><span style="color:{color};font-weight:600">{b['dpd']} days</span></td>
            <td><span style="background:{color};color:white;padding:2px 8px;border-radius:99px;font-size:12px">{b['risk_segment']}</span></td>
            <td>
                <button onclick="triggerCall('{b['id']}')"
                style="background:#3b82f6;color:white;border:none;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:11px;margin:2px">
                📞 Call
                </button>
                <button onclick="triggerSMS('{b['id']}')"
                style="background:#6b7280;color:white;border:none;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:11px;margin:2px">
                💬 SMS
                </button>
                <button onclick="triggerWhatsApp('{b['id']}')"
                style="background:#22c55e;color:white;border:none;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:11px;margin:2px">
                🟢 WA
                </button>
                <button onclick="triggerEmail('{b['id']}')"
                style="background:#f97316;color:white;border:none;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:11px;margin:2px">
                📧 Email
                </button>
            </td>
        </tr>"""

    ptp_rows = ""
    for p in ptps:
        ptp_rows += f"""
        <tr>
            <td>{p['borrower_id']}</td>
            <td>Rs {p['promised_amount']:,.0f}</td>
            <td>{p['promised_date']}</td>
            <td>{p['captured_at'][:16]}</td>
            <td><span style="background:#22c55e;color:white;padding:2px 8px;border-radius:99px;font-size:12px">{p['status']}</span></td>
        </tr>"""

    if not ptp_rows:
        ptp_rows = "<tr><td colspan='5' style='text-align:center;color:#888'>No PTPs captured yet</td></tr>"

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CFLO Voice Agent Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, sans-serif; background: #f8fafc; color: #1e293b; }}
        .header {{ background: #1e293b; color: white; padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; }}
        .header h1 {{ font-size: 20px; font-weight: 600; }}
        .header span {{ font-size: 13px; color: #94a3b8; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 24px 32px 0; }}
        .stat-card {{ background: white; border-radius: 10px; padding: 20px; border: 1px solid #e2e8f0; }}
        .stat-card .label {{ font-size: 13px; color: #64748b; margin-bottom: 8px; }}
        .stat-card .value {{ font-size: 28px; font-weight: 600; }}
        .section {{ margin: 24px 32px; background: white; border-radius: 10px; border: 1px solid #e2e8f0; overflow: hidden; }}
        .section-header {{ padding: 16px 20px; border-bottom: 1px solid #e2e8f0; font-weight: 600; font-size: 15px; display: flex; justify-content: space-between; align-items: center; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #f8fafc; padding: 10px 16px; text-align: left; font-size: 12px; color: #64748b; font-weight: 500; border-bottom: 1px solid #e2e8f0; }}
        td {{ padding: 12px 16px; font-size: 13px; border-bottom: 1px solid #f1f5f9; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: #f8fafc; }}
        #status {{ position: fixed; bottom: 24px; right: 24px; background: #1e293b; color: white; padding: 12px 20px; border-radius: 10px; font-size: 13px; display: none; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>CFLO Voice Agent</h1>
        <span>AI-powered debt collection platform</span>
    </div>

    <div class="stats">
        <div class="stat-card">
            <div class="label">Total borrowers</div>
            <div class="value" style="color:#3b82f6">{len(borrowers)}</div>
        </div>
        <div class="stat-card">
            <div class="label">Critical (S1/S2)</div>
            <div class="value" style="color:#ef4444">{sum(1 for b in borrowers if b['risk_segment'] in ['S1','S2'])}</div>
        </div>
        <div class="stat-card">
            <div class="label">PTPs captured</div>
            <div class="value" style="color:#22c55e">{len(ptps)}</div>
        </div>
        <div class="stat-card">
            <div class="label">Calls made</div>
            <div class="value" style="color:#8b5cf6">{len(calls)}</div>
        </div>
    </div>

    <div class="section">
        <div class="section-header">
            <span>Borrower accounts</span>
            <button onclick="triggerCampaign()" style="background:#3b82f6;color:white;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font-size:13px">Run smart campaign</button>
        </div>
        <table>
            <tr>
                <th>Name</th><th>Loan</th><th>Outstanding</th>
                <th>EMI</th><th>Due date</th><th>DPD</th>
                <th>Segment</th><th>Actions</th>
            </tr>
            {borrower_rows}
        </table>
    </div>

    <div class="section">
        <div class="section-header">PTP log</div>
        <table>
            <tr><th>Borrower</th><th>Amount</th><th>Promise date</th><th>Captured at</th><th>Status</th></tr>
            {ptp_rows}
        </table>
    </div>

    <div id="status"></div>

    <script>
        async function triggerCall(borrowerId) {{
            const status = document.getElementById('status');
            status.style.display = 'block';
            status.textContent = 'Initiating call...';
            try {{
                const res = await fetch('/call/borrower/' + borrowerId, {{method: 'POST'}});
                const data = await res.json();
                status.textContent = 'Call initiated! SID: ' + data.call_sid;
            }} catch(e) {{
                status.textContent = 'Error: ' + e.message;
            }}
            setTimeout(() => status.style.display = 'none', 4000);
        }}

        async function triggerSMS(borrowerId) {{
            const status = document.getElementById('status');
            status.style.display = 'block';
            status.textContent = 'Sending SMS...';
            try {{
                const res = await fetch('/communicate/sms/' + borrowerId, {{method: 'POST'}});
                const data = await res.json();
                status.textContent = data.status || data.error;
            }} catch(e) {{
                status.textContent = 'Error: ' + e.message;
            }}
            setTimeout(() => status.style.display = 'none', 4000);
        }}

        async function triggerWhatsApp(borrowerId) {{
            const status = document.getElementById('status');
            status.style.display = 'block';
            status.textContent = 'Sending WhatsApp...';
            try {{
                const res = await fetch('/communicate/whatsapp/' + borrowerId, {{method: 'POST'}});
                const data = await res.json();
                status.textContent = data.status || data.error;
            }} catch(e) {{
                status.textContent = 'Error: ' + e.message;
            }}
            setTimeout(() => status.style.display = 'none', 4000);
        }}

        async function triggerCampaign() {{
            const status = document.getElementById('status');
            status.style.display = 'block';
            status.textContent = 'Running smart campaign...';
            try {{
                const res = await fetch('/communicate/campaign', {{method: 'POST'}});
                const data = await res.json();
                status.textContent = 'Campaign done! ' + data.total + ' borrowers processed.';
            }} catch(e) {{
                status.textContent = 'Error: ' + e.message;
            }}
            setTimeout(() => status.style.display = 'none', 5000);
        }}

        async function triggerEmail(borrowerId) {{
            const status = document.getElementById('status');
            status.style.display = 'block';
            status.textContent = 'Sending email...';
            try {{
                const res = await fetch('/communicate/email/' + borrowerId, {{method: 'POST'}});
                const data = await res.json();
                status.textContent = data.status || data.error;
            }} catch(e) {{
                status.textContent = 'Error: ' + e.message;
            }}
            setTimeout(() => status.style.display = 'none', 4000);
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)