/**
 * Wing Theatre Controller — Bitfocus Companion Module
 * Developers: Mikkel Peter Larsen & Claude (Anthropic)
 * Credits: libwing by dannyfiresnake, protocol by Patrick-Gilles Maillot
 */
const { InstanceBase, runEntrypoint, InstanceStatus, combineRgb } = require('@companion-module/base')
const net = require('net')

class WingTheatreInstance extends InstanceBase {
  constructor(internal) {
    super(internal)
    this._socket = null
    this._buf = ''
    this._state = {
      current_cue_num: '', current_cue_name: '',
      next_cue_num: '',    next_cue_name: '',
      autoupdate: 'false', wing_connected: 'false',
      cue_count: '0',      fading: 'false',
    }
    this._reconnect_timer = null
  }

  async init(config) {
    this.config = config
    this._defineActions()
    this._defineFeedbacks()
    this._defineVariables()
    this._definePresets()
    this._connect()
  }

  async destroy() {
    this._stopReconnect()
    if (this._socket) { this._socket.destroy(); this._socket = null }
  }

  async configUpdated(config) {
    this.config = config
    if (this._socket) this._socket.destroy()
    this._connect()
  }

  getConfigFields() {
    return [
      { type: 'textinput', id: 'host', label: 'Wing Theatre IP', width: 8, default: '127.0.0.1' },
      { type: 'number',    id: 'port', label: 'TCP Port',        width: 4, default: 9000, min: 1024, max: 65535 },
    ]
  }

  _connect() {
    this._stopReconnect()
    const host = this.config && this.config.host ? this.config.host : '127.0.0.1'
    const port = this.config && this.config.port ? this.config.port : 9000
    this.updateStatus(InstanceStatus.Connecting)
    this._socket = new net.Socket()
    this._socket.setEncoding('utf8')
    this._socket.connect(port, host, () => {
      this.updateStatus(InstanceStatus.Ok)
      this._buf = ''
      this._send('GET_STATE')
    })
    this._socket.on('data', (data) => {
      this._buf += data
      let nl
      while ((nl = this._buf.indexOf('\n')) !== -1) {
        const line = this._buf.slice(0, nl).trim()
        this._buf = this._buf.slice(nl + 1)
        if (line) this._handleLine(line)
      }
    })
    this._socket.on('error', (err) => {
      this.updateStatus(InstanceStatus.ConnectionFailure, err.message)
      this._scheduleReconnect()
    })
    this._socket.on('close', () => {
      this.updateStatus(InstanceStatus.Disconnected)
      this._scheduleReconnect()
    })
  }

  _scheduleReconnect() {
    this._stopReconnect()
    this._reconnect_timer = setTimeout(() => this._connect(), 5000)
  }

  _stopReconnect() {
    if (this._reconnect_timer) { clearTimeout(this._reconnect_timer); this._reconnect_timer = null }
  }

  _send(cmd) {
    if (this._socket && this._socket.writable) this._socket.write(cmd + '\n')
  }

  _handleLine(line) {
    if (!line.startsWith('STATE ')) return
    const eq = line.indexOf('=')
    if (eq < 0) return
    const key = line.slice(6, eq).trim()
    const val = line.slice(eq + 1).trim()
    if (!(key in this._state)) return
    this._state[key] = val
    this.setVariableValues({ [key]: val })
    this.checkFeedbacks('autoupdate', 'wing_connected', 'fading', 'current_cue_num', 'current_cue_name')
  }

  _defineActions() {
    this.setActionDefinitions({
      go:        { name: 'GO — fire current cue',     options: [], callback: () => this._send('GO') },
      next_go:   { name: 'Next GO',                   options: [], callback: () => this._send('NEXT_GO') },
      prev_go:   { name: 'Previous GO',               options: [], callback: () => this._send('PREV_GO') },
      au_on:     { name: 'Auto Update ON',            options: [], callback: () => this._send('AU_ON') },
      au_off:    { name: 'Auto Update OFF',           options: [], callback: () => this._send('AU_OFF') },
      au_toggle: { name: 'Auto Update Toggle',        options: [], callback: () => this._send('AU_TOGGLE') },
      get_state: { name: 'Request full state update', options: [], callback: () => this._send('GET_STATE') },
      snap_go: {
        name: 'GO specific cue',
        options: [{ type: 'textinput', id: 'target', label: 'Cue number or name', default: '1' }],
        callback: function(a) { this._send('SNAP_GO ' + a.options.target) }.bind(this),
      },
      add_snap: {
        name: 'Add Snapshot',
        options: [{ type: 'textinput', id: 'name', label: 'Name (optional)', default: '' }],
        callback: function(a) {
          const n = (a.options.name || '').trim()
          this._send(n ? 'ADD_SNAP ' + n : 'ADD_SNAP')
        }.bind(this),
      },
    })
  }

  _defineFeedbacks() {
    const GREEN  = combineRgb(50, 200, 100)
    const YELLOW = combineRgb(230, 200, 0)
    const BLACK  = combineRgb(0, 0, 0)
    this.setFeedbackDefinitions({
      autoupdate:       { name: 'Auto Update is ON',         type: 'boolean', defaultStyle: { bgcolor: GREEN, color: BLACK },  options: [], callback: function() { return this._state.autoupdate === 'true' }.bind(this) },
      wing_connected:   { name: 'Wing is connected',         type: 'boolean', defaultStyle: { bgcolor: GREEN },                options: [], callback: function() { return this._state.wing_connected === 'true' }.bind(this) },
      fading:           { name: 'Fade in progress',          type: 'boolean', defaultStyle: { bgcolor: YELLOW, color: BLACK }, options: [], callback: function() { return this._state.fading === 'true' }.bind(this) },
      current_cue_num:  { name: 'Current cue is number',    type: 'boolean', defaultStyle: { bgcolor: GREEN },
        options: [{ type: 'textinput', id: 'num', label: 'Cue number (e.g. 001)', default: '001' }],
        callback: function(fb) { return this._state.current_cue_num === fb.options.num.trim() }.bind(this) },
      current_cue_name: { name: 'Current cue name contains', type: 'boolean', defaultStyle: { bgcolor: GREEN },
        options: [{ type: 'textinput', id: 'name', label: 'Name (partial match)', default: 'Scene' }],
        callback: function(fb) { return this._state.current_cue_name.toLowerCase().includes(fb.options.name.toLowerCase()) }.bind(this) },
    })
  }

  _defineVariables() {
    this.setVariableDefinitions([
      { variableId: 'current_cue_num',  name: 'Current cue number' },
      { variableId: 'current_cue_name', name: 'Current cue name' },
      { variableId: 'next_cue_num',     name: 'Next cue number' },
      { variableId: 'next_cue_name',    name: 'Next cue name' },
      { variableId: 'autoupdate',       name: 'Auto Update (true/false)' },
      { variableId: 'wing_connected',   name: 'Wing connected (true/false)' },
      { variableId: 'cue_count',        name: 'Total cues' },
      { variableId: 'fading',           name: 'Fade in progress (true/false)' },
    ])
    this.setVariableValues(this._state)
  }

  _definePresets() {
    const WHITE = combineRgb(255,255,255)
    const BLACK = combineRgb(0,0,0)
    const GREEN = combineRgb(50,200,100)
    const DARK  = combineRgb(30,30,30)
    this.setPresetDefinitions([
      { type:'button', category:'Wing Theatre', name:'GO',
        style:{text:'GO', size:'18', color:WHITE, bgcolor:combineRgb(0,120,50)},
        steps:[{down:[{actionId:'go',options:{}}],up:[]}], feedbacks:[] },
      { type:'button', category:'Wing Theatre', name:'GO + next cue name',
        style:{text:'GO\n$(wingtheatre:next_cue_name)', size:'14', color:WHITE, bgcolor:combineRgb(0,100,40)},
        steps:[{down:[{actionId:'go',options:{}}],up:[]}], feedbacks:[] },
      { type:'button', category:'Wing Theatre', name:'Current cue display',
        style:{text:'$(wingtheatre:current_cue_num)\n$(wingtheatre:current_cue_name)', size:'12', color:WHITE, bgcolor:DARK},
        steps:[{down:[{actionId:'get_state',options:{}}],up:[]}], feedbacks:[] },
      { type:'button', category:'Wing Theatre', name:'Auto Update toggle',
        style:{text:'AUTO\nUPDATE', size:'14', color:WHITE, bgcolor:DARK},
        steps:[{down:[{actionId:'au_toggle',options:{}}],up:[]}],
        feedbacks:[{feedbackId:'autoupdate',options:{},style:{bgcolor:GREEN,color:BLACK}}] },
      { type:'button', category:'Wing Theatre', name:'Wing connected indicator',
        style:{text:'WING\nCONNECTED', size:'12', color:WHITE, bgcolor:combineRgb(100,30,30)},
        steps:[{down:[],up:[]}],
        feedbacks:[{feedbackId:'wing_connected',options:{},style:{bgcolor:GREEN}}] },
    ])
  }
}

runEntrypoint(WingTheatreInstance, [])
