from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from routes import router as api_router
from models import Base, engine

load_dotenv()

app = FastAPI(title="QueueBite API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    # Seed demo restaurant so UI works out of the box
    from models import SessionLocal, Restaurant
    import uuid

    db = SessionLocal()
    try:
        demo_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        existing = db.query(Restaurant).filter(Restaurant.id == demo_id).first()
        if not existing:
            db.add(
                Restaurant(id=demo_id, name="Demo Restaurant", address="123 Main St")
            )
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def landing():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QueueBite - AI Restaurant Queue Management</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: { orange: '#f97316', red: '#ef4444' },
        dark: { bg: '#0a0a0a', card: '#171717', border: '#262626', hover: '#1f1f1f' }
      }
    }
  }
}
</script>
<style>
.gradient-text{background:linear-gradient(135deg,#f97316,#ef4444);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.gradient-btn{background:linear-gradient(135deg,#f97316,#ef4444)}
.gradient-btn:hover{background:linear-gradient(135deg,#ea580c,#dc2626)}
.spinner{border:3px solid #262626;border-top:3px solid #f97316;border-radius:50%;width:20px;height:20px;animation:spin .8s linear infinite;display:inline-block}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body class="bg-[#0a0a0a] text-[#e5e5e5] min-h-screen">

<div class="max-w-3xl mx-auto px-4 py-8 sm:py-12">

  <!-- Hero -->
  <div class="text-center mb-10">
    <h1 class="text-5xl sm:text-6xl font-extrabold gradient-text mb-2">QueueBite</h1>
    <p class="text-lg text-neutral-400 mb-4">Scan, wait, dine &mdash; no more standing in line.</p>
    <div class="flex justify-center gap-2 flex-wrap">
      <span class="px-3 py-1 rounded-full text-xs font-semibold bg-violet-500/10 text-violet-400 border border-violet-500/25">AI-Powered</span>
      <span class="px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/25">DigitalOcean</span>
      <span class="px-3 py-1 rounded-full text-xs font-semibold bg-green-500/10 text-green-400 border border-green-500/25">Live</span>
    </div>
  </div>

  <!-- How It Works -->
  <div class="bg-[#171717] border border-[#262626] rounded-xl p-5 sm:p-6 mb-4">
    <h2 class="text-lg font-bold text-neutral-100 mb-3">How It Works</h2>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="text-center"><div class="text-2xl mb-1">📱</div><p class="text-sm font-medium text-neutral-200">1. Join the Queue</p><p class="text-xs text-neutral-500">Enter your name and party size to get in line.</p></div>
      <div class="text-center"><div class="text-2xl mb-1">⏱️</div><p class="text-sm font-medium text-neutral-200">2. AI Predicts Wait</p><p class="text-xs text-neutral-500">Our AI estimates your wait time based on real-time data.</p></div>
      <div class="text-center"><div class="text-2xl mb-1">🍽️</div><p class="text-sm font-medium text-neutral-200">3. Get Seated</p><p class="text-xs text-neutral-500">Check your status anytime and get notified when ready.</p></div>
    </div>
  </div>

  <!-- Section 1: Join Queue -->
  <div class="bg-[#171717] border border-[#262626] rounded-xl p-5 sm:p-6 mb-4">
    <h2 class="text-lg font-bold text-neutral-100 mb-1">Join Queue</h2>
    <p class="text-sm text-neutral-500 mb-4">Add yourself to a restaurant's waiting list.</p>
    <form id="joinForm" class="space-y-3" onsubmit="return handleJoin(event)">
      <input type="hidden" id="joinRestaurantId" value="00000000-0000-0000-0000-000000000001"/>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Your Name</label>
          <input type="text" id="joinName" placeholder="Jane Doe" required
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Party Size</label>
          <input type="number" id="joinPartySize" value="2" min="1" required
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
      </div>
      <button type="submit" class="gradient-btn text-white text-sm font-semibold px-5 py-2.5 rounded-lg w-full sm:w-auto transition-all">
        Join Queue
      </button>
    </form>
    <div id="joinLoading" class="hidden mt-3"><span class="spinner"></span> <span class="text-sm text-neutral-400 ml-2">Joining queue...</span></div>
    <div id="joinResult" class="hidden mt-4"></div>
    <div id="joinError" class="hidden mt-3 text-red-400 text-sm"></div>
  </div>

  <!-- Section 2: Check Status -->
  <div class="bg-[#171717] border border-[#262626] rounded-xl p-5 sm:p-6 mb-4">
    <h2 class="text-lg font-bold text-neutral-100 mb-1">Check Queue Status</h2>
    <p class="text-sm text-neutral-500 mb-4">Look up your current position in line.</p>
    <form id="statusForm" class="space-y-3" onsubmit="return handleStatus(event)">
      <div>
        <label class="block text-xs font-medium text-neutral-400 mb-1">Queue ID</label>
        <input type="text" id="statusQueueId" placeholder="Will auto-fill after joining" required
          class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
      </div>
      <button type="submit" class="gradient-btn text-white text-sm font-semibold px-5 py-2.5 rounded-lg w-full sm:w-auto transition-all">
        Check Status
      </button>
    </form>
    <div id="statusLoading" class="hidden mt-3"><span class="spinner"></span> <span class="text-sm text-neutral-400 ml-2">Checking status...</span></div>
    <div id="statusResult" class="hidden mt-4"></div>
    <div id="statusError" class="hidden mt-3 text-red-400 text-sm"></div>
  </div>

  <!-- Section 3: AI Predict Wait Time -->
  <div class="bg-[#171717] border border-[#262626] rounded-xl p-5 sm:p-6 mb-4">
    <h2 class="text-lg font-bold text-neutral-100 mb-1">AI Predict Wait Time</h2>
    <p class="text-sm text-neutral-500 mb-4">Get an AI-powered estimate of how long the wait will be.</p>
    <form id="predictForm" class="space-y-3" onsubmit="return handlePredict(event)">
      <input type="hidden" id="predictRestaurantId" value="00000000-0000-0000-0000-000000000001"/>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Party Size</label>
          <input type="number" id="predictPartySize" value="2" min="1" required
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Current Queue Length</label>
          <input type="number" id="predictQueueLen" value="5" min="0" required
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Day of Week (0=Mon, 6=Sun)</label>
          <input type="number" id="predictDayOfWeek" value="4" min="0" max="6" required
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Time (HH:MM)</label>
          <input type="time" id="predictTime" value="19:00" required
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
      </div>
      <button type="submit" class="gradient-btn text-white text-sm font-semibold px-5 py-2.5 rounded-lg w-full sm:w-auto transition-all">
        Predict Wait Time
      </button>
    </form>
    <div id="predictLoading" class="hidden mt-3"><span class="spinner"></span> <span class="text-sm text-neutral-400 ml-2">Running AI prediction...</span></div>
    <div id="predictResult" class="hidden mt-4"></div>
    <div id="predictError" class="hidden mt-3 text-red-400 text-sm"></div>
  </div>

  <!-- Section 4: AI Forecast Demand -->
  <div class="bg-[#171717] border border-[#262626] rounded-xl p-5 sm:p-6 mb-4">
    <h2 class="text-lg font-bold text-neutral-100 mb-1">AI Forecast Demand</h2>
    <p class="text-sm text-neutral-500 mb-4">Predict upcoming restaurant demand based on historical data.</p>
    <form id="forecastForm" class="space-y-3" onsubmit="return handleForecast(event)">
      <input type="hidden" id="forecastRestaurantId" value="00000000-0000-0000-0000-000000000001"/>
      <div>
        <label class="block text-xs font-medium text-neutral-400 mb-1">Past 7 Days Footfall (comma-separated, exactly 7 numbers)</label>
        <input type="text" id="forecastFootfall" value="120,135,98,142,160,155,130" required placeholder="e.g. 120,135,98,142,160,155,130"
          class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Local Events (comma-separated)</label>
          <input type="text" id="forecastEvents" value="concert,sports game" placeholder="e.g. concert, food festival"
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
        <div>
          <label class="block text-xs font-medium text-neutral-400 mb-1">Weather</label>
          <input type="text" id="forecastWeather" value="sunny" placeholder="e.g. sunny, rainy, cloudy"
            class="w-full bg-[#0a0a0a] border border-[#262626] rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-colors"/>
        </div>
      </div>
      <button type="submit" class="gradient-btn text-white text-sm font-semibold px-5 py-2.5 rounded-lg w-full sm:w-auto transition-all">
        Forecast Demand
      </button>
    </form>
    <div id="forecastLoading" class="hidden mt-3"><span class="spinner"></span> <span class="text-sm text-neutral-400 ml-2">Forecasting demand...</span></div>
    <div id="forecastResult" class="hidden mt-4"></div>
    <div id="forecastError" class="hidden mt-3 text-red-400 text-sm"></div>
  </div>

  <!-- Footer -->
  <p class="text-center text-xs text-neutral-600 mt-8">
    Generated by <a href="https://github.com/Two-Weeks-Team/vibeDeploy" class="text-orange-500 hover:text-orange-400 transition-colors">vibeDeploy</a>
    &bull; Powered by <a href="https://www.digitalocean.com/products/gradient-ai" class="text-orange-500 hover:text-orange-400 transition-colors">DigitalOcean Gradient AI</a>
    &bull; <a href="/docs" class="text-neutral-500 hover:text-neutral-400 transition-colors">API Docs</a>
  </p>
</div>

<script>
function showLoading(id){document.getElementById(id+'Loading').classList.remove('hidden');document.getElementById(id+'Result').classList.add('hidden');document.getElementById(id+'Error').classList.add('hidden')}
function hideLoading(id){document.getElementById(id+'Loading').classList.add('hidden')}
function showError(id,msg){hideLoading(id);const el=document.getElementById(id+'Error');el.textContent=msg;el.classList.remove('hidden')}
function showResult(id,html){hideLoading(id);const el=document.getElementById(id+'Result');el.innerHTML=html;el.classList.remove('hidden')}

function resultCard(pairs){
  let rows=pairs.map(([k,v])=>'<div class="flex justify-between py-1.5 border-b border-[#262626] last:border-0"><span class="text-neutral-400 text-sm">'+k+'</span><span class="text-neutral-100 text-sm font-medium">'+v+'</span></div>').join('');
  return '<div class="border border-green-500/30 bg-green-500/5 rounded-lg p-4">'+rows+'</div>';
}

async function apiCall(url,options){
  const res=await fetch(url,options);
  const data=await res.json();
  if(!res.ok){
    const detail=data.detail;
    if(typeof detail==='string') throw new Error(detail);
    if(Array.isArray(detail)) throw new Error(detail.map(e=>e.msg||JSON.stringify(e)).join('; '));
    throw new Error(JSON.stringify(data));
  }
  return data;
}

async function handleJoin(e){
  e.preventDefault();
  showLoading('join');
  try{
    const body={restaurant_id:document.getElementById('joinRestaurantId').value.trim(),name:document.getElementById('joinName').value.trim(),party_size:parseInt(document.getElementById('joinPartySize').value)};
    const data=await apiCall('/api/v1/customers/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(data.queue_id){document.getElementById('statusQueueId').value=data.queue_id}
    showResult('join',resultCard([['Queue ID',data.queue_id||'N/A'],['Position',data.position!=null?data.position:'N/A'],['Estimated Wait',data.estimated_wait_minutes!=null?data.estimated_wait_minutes+' min':'N/A']]));
  }catch(err){showError('join','Error: '+err.message)}
}

async function handleStatus(e){
  e.preventDefault();
  showLoading('status');
  try{
    const qid=document.getElementById('statusQueueId').value.trim();
    if(!qid){throw new Error('Please enter a Queue ID')}
    const data=await apiCall('/api/v1/customers/'+encodeURIComponent(qid)+'/status',{method:'GET',headers:{'Content-Type':'application/json'}});
    showResult('status',resultCard([['Current Position',data.current_position!=null?data.current_position:'N/A'],['Estimated Wait',data.estimated_wait_minutes!=null?data.estimated_wait_minutes+' min':'N/A'],['AI Confidence',data.ai_confidence!=null?(data.ai_confidence*100).toFixed(1)+'%':'N/A']]));
  }catch(err){showError('status','Error: '+err.message)}
}

async function handlePredict(e){
  e.preventDefault();
  showLoading('predict');
  try{
    const body={restaurant_id:document.getElementById('predictRestaurantId').value.trim(),party_size:parseInt(document.getElementById('predictPartySize').value),current_queue_length:parseInt(document.getElementById('predictQueueLen').value),day_of_week:parseInt(document.getElementById('predictDayOfWeek').value),time_of_day:document.getElementById('predictTime').value};
    const data=await apiCall('/api/v1/ai/predict-wait-time',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    showResult('predict',resultCard([['Predicted Wait',data.predicted_wait_minutes!=null?data.predicted_wait_minutes+' min':'N/A'],['Confidence',data.confidence!=null?(data.confidence*100).toFixed(1)+'%':'N/A']]));
  }catch(err){showError('predict','Error: '+err.message)}
}

async function handleForecast(e){
  e.preventDefault();
  showLoading('forecast');
  try{
    const footfallRaw=document.getElementById('forecastFootfall').value.trim();
    const footfall=footfallRaw.split(',').map(s=>parseInt(s.trim())).filter(n=>!isNaN(n));
    if(footfall.length!==7){throw new Error('Please enter exactly 7 footfall numbers, comma-separated')}
    const eventsRaw=document.getElementById('forecastEvents').value.trim();
    const events=eventsRaw?eventsRaw.split(',').map(s=>s.trim()).filter(Boolean):[];
    const body={restaurant_id:document.getElementById('forecastRestaurantId').value.trim(),past_7_days_footfall:footfall,local_events:events,weather:document.getElementById('forecastWeather').value.trim()};
    const data=await apiCall('/api/v1/ai/forecast-demand',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    showResult('forecast',resultCard([['Peak Hour',data.peak_hour!=null?data.peak_hour:'N/A'],['Expected Party Increase',data.expected_party_increase_percent!=null?data.expected_party_increase_percent+'%':'N/A']]));
  }catch(err){showError('forecast','Error: '+err.message)}
}
</script>
</body>
</html>"""
