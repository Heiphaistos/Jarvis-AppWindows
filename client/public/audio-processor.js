class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = [];
    this._TARGET = 4096;
  }

  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) this._buf.push(ch[i]);
    while (this._buf.length >= this._TARGET) {
      this.port.postMessage(this._buf.splice(0, this._TARGET));
    }
    return true;
  }
}
registerProcessor("audio-processor", AudioProcessor);
