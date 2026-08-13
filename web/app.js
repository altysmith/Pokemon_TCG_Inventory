const photoInput = document.querySelector('#photo');
const canvas = document.querySelector('#canvas');
const ctx = canvas.getContext('2d');
const stage = document.querySelector('#stage');
const placeholder = document.querySelector('#placeholder');
const scanButton = document.querySelector('#scan');
const saveButton = document.querySelector('#save');
const instruction = document.querySelector('#instruction');
const state = document.querySelector('#state');
const message = document.querySelector('#message');
const literalOcr = document.querySelector('#literal_ocr');
const ocrEngine = document.querySelector('#ocr_engine');
const scanTiming = document.querySelector('#scan_timing');
const regulationMark = document.querySelector('#regulation_mark');
const setCode = document.querySelector('#set_code');
const cardNumber = document.querySelector('#card_number');
const setTotal = document.querySelector('#set_total');
const readerName = document.querySelector('#reader_name');
const startCameraButton = document.querySelector('#start_camera');
const captureFrameButton = document.querySelector('#capture_frame');
const nextCardButton = document.querySelector('#next_card');
const stopCameraButton = document.querySelector('#stop_camera');
const cameraSelect = document.querySelector('#camera_device');
const cameraFrame = document.querySelector('#camera_frame');
const cameraVideo = document.querySelector('#camera_video');
const reuseSelection = document.querySelector('#reuse_selection');
const clearSelectionButton = document.querySelector('#clear_selection');
const lookupButton = document.querySelector('#lookup_card');
const lookupState = document.querySelector('#lookup_state');
const lookupResult = document.querySelector('#lookup_result');
const lookupImage = document.querySelector('#lookup_image');
const lookupName = document.querySelector('#lookup_name');
const lookupIdentity = document.querySelector('#lookup_identity');
const lookupSource = document.querySelector('#lookup_source');
const lookupMessage = document.querySelector('#lookup_message');
const inventoryQuantity = document.querySelector('#inventory_quantity');
const inventoryAddQuantity = document.querySelector('#inventory_add_quantity');
const addInventoryButton = document.querySelector('#add_inventory');
const undoInventoryButton = document.querySelector('#undo_inventory');
const inventoryMessage = document.querySelector('#inventory_message');
const UI_ITERATION = 13;
const CARD_GUIDE = {top: 0.07, height: 0.86, aspect: 5 / 7, maxWidth: 0.82};
const IDENTIFIER_GUIDE = {left: 0.06, top: 0.915, width: 0.26, height: 0.055};

let image = null;
let imageName = '';
let selection = null;
let selectionNormalized = null;
let lockedSelectionNormalized = null;
let start = null;
let rawOcr = '';
let scanInProgress = false;
let scanId = '';
let versionReady = false;
let mediaStream = null;
let capturedFromCamera = false;
let lastLookupStatus = 'not_checked';
let currentInventoryEventId = 0;

function resetOcrResult() {
  rawOcr = '';
  scanId = '';
  literalOcr.textContent = 'Waiting for scan';
  ocrEngine.textContent = '';
  scanTiming.textContent = 'SCAN TIME: NOT RUN YET';
  regulationMark.value = '';
  setCode.value = '';
  cardNumber.value = '';
  setTotal.value = '';
  readerName.textContent = '-';
  saveButton.disabled = true;
  resetLookup();
}

function updateLookupAvailability() {
  lookupButton.disabled = !setCode.value.trim() || !cardNumber.value.trim();
}

function resetLookup() {
  lastLookupStatus = 'not_checked';
  lookupState.textContent = 'NOT CHECKED';
  lookupState.className = 'state';
  lookupResult.hidden = true;
  lookupImage.hidden = true;
  lookupImage.removeAttribute('src');
  lookupName.textContent = '';
  lookupIdentity.textContent = '';
  lookupSource.textContent = '';
  lookupButton.hidden = false;
  lookupMessage.textContent = 'Uses the local Malie catalog only. Nothing is added automatically.';
  resetInventoryControls();
  updateLookupAvailability();
}

function resetInventoryControls() {
  currentInventoryEventId = 0;
  inventoryQuantity.textContent = '-';
  inventoryAddQuantity.value = '1';
  addInventoryButton.disabled = true;
  undoInventoryButton.disabled = true;
  inventoryMessage.textContent = 'Available only after one exact, conflict-free catalog match.';
}

function blockForVersion(detail) {
  versionReady = false;
  photoInput.disabled = true;
  startCameraButton.disabled = true;
  captureFrameButton.disabled = true;
  scanButton.disabled = true;
  saveButton.disabled = true;
  stopMediaTracks();
  state.textContent = 'RESTART NEEDED';
  state.className = 'state bad';
  instruction.textContent = detail;
  message.textContent = 'Close the scanner command window, run run_scanner.bat again, then refresh this page.';
}

async function verifyVersion() {
  try {
    const response = await fetch('/health', {cache: 'no-store'});
    const health = await response.json();
    if (!response.ok || !health.ok || health.iteration !== UI_ITERATION) {
      const found = health.iteration ? `Iteration ${health.iteration}` : 'an older server';
      blockForVersion(`This Iteration ${UI_ITERATION} page is connected to ${found}.`);
      return;
    }
    if (!health.primary_ocr_available) {
      blockForVersion('RapidOCR is not installed, so reliable scanning is unavailable.');
      message.textContent = 'Run the project dependency installation, restart the scanner, then refresh this page.';
      return;
    }
    if (!health.local_catalog_available) {
      blockForVersion('The local card database has not been built yet.');
      message.textContent = 'Double-click update_card_database.bat, then restart the scanner.';
      return;
    }
    versionReady = true;
    photoInput.disabled = false;
    startCameraButton.disabled = !navigator.mediaDevices?.getUserMedia;
    if (startCameraButton.disabled) {
      message.textContent = 'This browser does not provide camera access. Photo upload is still available.';
    }
  } catch {
    blockForVersion(`Iteration ${UI_ITERATION} cannot reach the local scanner.`);
  }
}

function fitImage() {
  if (!image) return;
  const maxWidth = Math.max(300, stage.clientWidth - 2);
  const maxHeight = Math.max(340, window.innerHeight - 285);
  const scale = Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight, 1);
  canvas.width = Math.round(image.naturalWidth * scale);
  canvas.height = Math.round(image.naturalHeight * scale);
  canvas.style.display = 'block';
  if (selectionNormalized) {
    selection = [
      selectionNormalized[0] * canvas.width,
      selectionNormalized[1] * canvas.height,
      selectionNormalized[2] * canvas.width,
      selectionNormalized[3] * canvas.height,
    ];
  }
  draw();
}

function sizeCameraFrame() {
  if (!cameraVideo.videoWidth || !cameraVideo.videoHeight) return;
  const maxWidth = Math.max(300, stage.clientWidth - 2);
  const maxHeight = Math.max(340, window.innerHeight - 285);
  const scale = Math.min(maxWidth / cameraVideo.videoWidth, maxHeight / cameraVideo.videoHeight, 1);
  cameraFrame.style.width = `${Math.round(cameraVideo.videoWidth * scale)}px`;
  cameraFrame.style.height = `${Math.round(cameraVideo.videoHeight * scale)}px`;
}

function draw() {
  if (!image) return;
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  if (selection) {
    const [x1, y1, x2, y2] = selection;
    ctx.fillStyle = 'rgba(0, 0, 0, .32)';
    ctx.fillRect(0, 0, canvas.width, y1);
    ctx.fillRect(0, y2, canvas.width, canvas.height - y2);
    ctx.fillRect(0, y1, x1, y2 - y1);
    ctx.fillRect(x2, y1, canvas.width - x2, y2 - y1);
    ctx.strokeStyle = '#32d7d4';
    ctx.lineWidth = 3;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  }
}

function pointerPosition(event) {
  const box = canvas.getBoundingClientRect();
  return [
    Math.max(0, Math.min(canvas.width, (event.clientX - box.left) * canvas.width / box.width)),
    Math.max(0, Math.min(canvas.height, (event.clientY - box.top) * canvas.height / box.height)),
  ];
}

function timestampName() {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '_');
  return `webcam_${stamp}.png`;
}

function fixedIdentifierSelection(frameWidth, frameHeight) {
  const cardHeight = frameHeight * CARD_GUIDE.height;
  const cardWidth = Math.min(cardHeight * CARD_GUIDE.aspect, frameWidth * CARD_GUIDE.maxWidth);
  const cardLeft = (frameWidth - cardWidth) / 2;
  const cardTop = frameHeight * CARD_GUIDE.top;
  return [
    (cardLeft + cardWidth * IDENTIFIER_GUIDE.left) / frameWidth,
    (cardTop + cardHeight * IDENTIFIER_GUIDE.top) / frameHeight,
    (cardLeft + cardWidth * (IDENTIFIER_GUIDE.left + IDENTIFIER_GUIDE.width)) / frameWidth,
    (cardTop + cardHeight * (IDENTIFIER_GUIDE.top + IDENTIFIER_GUIDE.height)) / frameHeight,
  ];
}

function loadImageSource(source, name, useLockedSelection = false) {
  const loaded = new Image();
  loaded.onload = () => {
    image = loaded;
    imageName = name;
    selectionNormalized = useLockedSelection && lockedSelectionNormalized
      ? [...lockedSelectionNormalized]
      : null;
    selection = null;
    resetOcrResult();
    stage.classList.remove('empty');
    placeholder.style.display = 'none';
    cameraFrame.hidden = true;
    fitImage();
    if (selectionNormalized) {
      state.textContent = 'FRAME CAPTURED';
      instruction.textContent = 'Reusing the saved text selection and reading this card automatically...';
      scanButton.disabled = false;
      void scanSelection();
    } else {
      state.textContent = 'SELECT AREA';
      instruction.textContent = 'Drag a tight box around only the letters and numbers. This can be reused for later cards.';
      scanButton.disabled = true;
    }
  };
  loaded.onerror = () => {
    state.textContent = 'IMAGE ERROR';
    state.className = 'state bad';
    message.textContent = 'The captured image could not be opened.';
  };
  loaded.src = source;
}

async function refreshCameraList() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  const current = cameraSelect.value;
  const devices = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === 'videoinput');
  cameraSelect.replaceChildren(new Option('Default camera', ''));
  devices.forEach((device, index) => {
    cameraSelect.add(new Option(device.label || `Camera ${index + 1}`, device.deviceId));
  });
  if ([...cameraSelect.options].some(option => option.value === current)) {
    cameraSelect.value = current;
  }
  cameraSelect.disabled = devices.length < 2;
}

function stopMediaTracks() {
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
  }
  mediaStream = null;
  cameraVideo.pause();
  cameraVideo.srcObject = null;
  captureFrameButton.disabled = true;
  nextCardButton.disabled = true;
  stopCameraButton.disabled = true;
  cameraSelect.disabled = true;
  if (versionReady) startCameraButton.disabled = !navigator.mediaDevices?.getUserMedia;
}

function showCameraError(error) {
  stopMediaTracks();
  cameraFrame.hidden = true;
  canvas.style.display = image ? 'block' : 'none';
  if (!image) {
    stage.classList.add('empty');
    placeholder.style.display = 'block';
  }
  state.textContent = 'CAMERA ERROR';
  state.className = 'state bad';
  instruction.textContent = 'The camera could not be started.';
  message.textContent = `${error.message || error}. Close other camera apps, then try Start camera again.`;
}

async function startCamera() {
  if (!versionReady || !navigator.mediaDevices?.getUserMedia) return;
  stopMediaTracks();
  resetOcrResult();
  state.textContent = 'STARTING CAMERA...';
  state.className = 'state';
  instruction.textContent = 'Allow camera access if the browser asks.';
  const selectedDevice = cameraSelect.value;
  const videoConstraints = {
    width: {ideal: 3840},
    height: {ideal: 2160},
    frameRate: {ideal: 30, max: 30},
  };
  if (selectedDevice) videoConstraints.deviceId = {exact: selectedDevice};
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({video: videoConstraints, audio: false});
    const track = mediaStream.getVideoTracks()[0];
    track.addEventListener('ended', () => {
      if (mediaStream) showCameraError(new Error('The camera stream ended.'));
    }, {once: true});
    cameraVideo.srcObject = mediaStream;
    await cameraVideo.play();
    await refreshCameraList();
    image = null;
    selection = null;
    selectionNormalized = null;
    capturedFromCamera = true;
    canvas.style.display = 'none';
    cameraFrame.hidden = false;
    placeholder.style.display = 'none';
    stage.classList.remove('empty');
    sizeCameraFrame();
    startCameraButton.disabled = true;
    captureFrameButton.disabled = false;
    stopCameraButton.disabled = false;
    state.textContent = 'CAMERA LIVE';
    state.className = 'state good';
    const settings = track.getSettings();
    instruction.textContent = 'Slide a card into the taped position, align it with the guide, then capture one frame.';
    message.textContent = `Camera active${settings.width ? ` at ${settings.width}x${settings.height}` : ''}. It will be released when you press Stop camera or close this page.`;
  } catch (error) {
    showCameraError(error);
  }
}

function captureFrame() {
  if (!mediaStream || !cameraVideo.videoWidth || !cameraVideo.videoHeight) return;
  const frame = document.createElement('canvas');
  frame.width = cameraVideo.videoWidth;
  frame.height = cameraVideo.videoHeight;
  frame.getContext('2d').drawImage(cameraVideo, 0, 0, frame.width, frame.height);
  cameraVideo.pause();
  captureFrameButton.disabled = true;
  nextCardButton.disabled = false;
  if (reuseSelection.checked && !lockedSelectionNormalized) {
    lockedSelectionNormalized = fixedIdentifierSelection(frame.width, frame.height);
    clearSelectionButton.disabled = false;
  }
  loadImageSource(frame.toDataURL('image/png'), timestampName(), reuseSelection.checked);
}

async function showNextCard() {
  if (!mediaStream || scanInProgress) return;
  image = null;
  selection = null;
  selectionNormalized = null;
  resetOcrResult();
  canvas.style.display = 'none';
  cameraFrame.hidden = false;
  sizeCameraFrame();
  try {
    await cameraVideo.play();
    captureFrameButton.disabled = false;
    nextCardButton.disabled = true;
    state.textContent = 'CAMERA LIVE';
    state.className = 'state good';
    instruction.textContent = lockedSelectionNormalized
      ? 'Slide in the next card. Only the fixed bottom-left identifier box will be read.'
      : 'Slide in the next card. Capture it, then select its text area.';
    message.textContent = 'The camera remains open only for this scanning session.';
  } catch (error) {
    showCameraError(error);
  }
}

function stopCamera() {
  const wasShowingCamera = !cameraFrame.hidden;
  stopMediaTracks();
  cameraFrame.hidden = true;
  if (!image || wasShowingCamera) {
    image = null;
    canvas.style.display = 'none';
    stage.classList.add('empty');
    placeholder.style.display = 'block';
    resetOcrResult();
  }
  state.textContent = 'CAMERA STOPPED';
  state.className = 'state';
  instruction.textContent = 'The camera has been released. Start it again or choose a photo.';
  message.textContent = 'No application should still be holding the camera.';
}

photoInput.addEventListener('change', () => {
  if (!versionReady) return;
  const file = photoInput.files[0];
  if (!file) return;
  stopMediaTracks();
  capturedFromCamera = false;
  const url = URL.createObjectURL(file);
  loadImageSource(url, file.name, false);
  setTimeout(() => URL.revokeObjectURL(url), 30000);
});

canvas.addEventListener('pointerdown', event => {
  if (scanInProgress) return;
  start = pointerPosition(event);
  selection = [start[0], start[1], start[0], start[1]];
  canvas.setPointerCapture(event.pointerId);
  draw();
});
canvas.addEventListener('pointermove', event => {
  if (!start || scanInProgress) return;
  const end = pointerPosition(event);
  selection = [Math.min(start[0], end[0]), Math.min(start[1], end[1]), Math.max(start[0], end[0]), Math.max(start[1], end[1])];
  draw();
});
canvas.addEventListener('pointerup', () => {
  if (scanInProgress) return;
  start = null;
  const valid = selection && selection[2] - selection[0] > 10 && selection[3] - selection[1] > 5;
  scanButton.disabled = !valid;
  if (valid) {
    selectionNormalized = [
      selection[0] / canvas.width,
      selection[1] / canvas.height,
      selection[2] / canvas.width,
      selection[3] / canvas.height,
    ];
    if (reuseSelection.checked) {
      lockedSelectionNormalized = [...selectionNormalized];
      clearSelectionButton.disabled = false;
    }
    instruction.textContent = 'Selection complete. Reading it automatically...';
    void scanSelection();
  }
});

async function scanSelection() {
  if (!versionReady || !image || !selection || scanInProgress) return;
  scanInProgress = true;
  scanId = '';
  saveButton.disabled = true;
  nextCardButton.disabled = true;
  const [x1, y1, x2, y2] = selection;
  const scaleX = image.naturalWidth / canvas.width;
  const scaleY = image.naturalHeight / canvas.height;
  const crop = document.createElement('canvas');
  crop.width = Math.round((x2 - x1) * scaleX);
  crop.height = Math.round((y2 - y1) * scaleY);
  crop.getContext('2d').drawImage(image, x1 * scaleX, y1 * scaleY, crop.width, crop.height, 0, 0, crop.width, crop.height);
  scanButton.disabled = true;
  state.textContent = 'READING...';
  state.className = 'state';
  const scanStartedAt = performance.now();
  let readingSeconds = 0;
  scanTiming.textContent = 'SCAN TIME: 0.0s (RUNNING)';
  message.textContent = 'Reading the card identifier. Clear cards use one quick pass; difficult cards automatically get additional treatments...';
  const readingTimer = window.setInterval(() => {
    readingSeconds = Math.floor((performance.now() - scanStartedAt) / 1000);
    scanTiming.textContent = `SCAN TIME: ${((performance.now() - scanStartedAt) / 1000).toFixed(1)}s (RUNNING)`;
    message.textContent = `Still reading the selected identifier (${readingSeconds}s). Please wait before moving to the next card...`;
  }, 100);
  try {
    const response = await fetch('/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        image: crop.toDataURL('image/png'),
        image_name: imageName,
        iteration: UI_ITERATION,
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Scan failed');
    const totalScanSeconds = (performance.now() - scanStartedAt) / 1000;
    const ocrSeconds = Number(result.ocr_elapsed_seconds);
    scanTiming.textContent = Number.isFinite(ocrSeconds)
      ? `SCAN TIME: ${totalScanSeconds.toFixed(2)}s TOTAL / ${ocrSeconds.toFixed(2)}s OCR`
      : `SCAN TIME: ${totalScanSeconds.toFixed(2)}s TOTAL`;
    if (result.iteration !== UI_ITERATION) {
      blockForVersion(`This page is Iteration ${UI_ITERATION}, but the server returned Iteration ${result.iteration || 'unknown'}.`);
      return;
    }
    scanId = result.scan_id || '';
    rawOcr = result.raw_ocr || '';
    literalOcr.textContent = rawOcr || 'No text detected';
    ocrEngine.textContent = result.ocr_engine ? `Reader: ${result.ocr_engine}` : '';
    regulationMark.value = result.regulation_mark || '';
    setCode.value = result.set_code || '';
    cardNumber.value = result.card_number || '';
    setTotal.value = result.set_total || '';
    resetLookup();
    readerName.textContent = result.ocr_engine || 'No reader result';
    state.textContent = rawOcr ? 'TEXT READ' : 'NO TEXT';
    state.className = `state ${rawOcr ? 'good' : 'bad'}`;
    message.textContent = rawOcr
      ? `Literal OCR: "${rawOcr}". Correct the fields, then save.`
      : 'No text was detected. Correct the fields anyway and save this no-read example.';
    saveButton.disabled = !scanId;
    if (setCode.value.trim() && cardNumber.value.trim()) {
      await lookupCurrentCard();
    }
  } catch (error) {
    scanTiming.textContent = `SCAN TIME: ${((performance.now() - scanStartedAt) / 1000).toFixed(2)}s / ERROR`;
    state.textContent = 'SCAN ERROR';
    state.className = 'state bad';
    message.textContent = error.message;
  } finally {
    window.clearInterval(readingTimer);
    scanInProgress = false;
    scanButton.disabled = !versionReady || !selection;
    nextCardButton.disabled = !mediaStream;
    if (versionReady) {
      if (lastLookupStatus === 'accepted') {
        instruction.textContent = 'Exact visual match found. No corrections are needed; save the OCR reading, then press Next card.';
      } else if (lastLookupStatus === 'no_match') {
        instruction.textContent = 'No exact match was found. Correct the editable fields, then press Find this card.';
      } else if (lastLookupStatus === 'review') {
        instruction.textContent = 'Review the displayed card and correct a field only if the identity or printed total is wrong.';
      } else {
        instruction.textContent = capturedFromCamera
          ? 'Correct and save this reading, then press Next card.'
          : 'Drag a new box to scan another area, or use Rescan Selection.';
      }
    }
  }
}

scanButton.addEventListener('click', () => void scanSelection());
startCameraButton.addEventListener('click', () => void startCamera());
captureFrameButton.addEventListener('click', captureFrame);
nextCardButton.addEventListener('click', () => void showNextCard());
stopCameraButton.addEventListener('click', stopCamera);
cameraSelect.addEventListener('change', () => {
  if (mediaStream) void startCamera();
});
reuseSelection.addEventListener('change', () => {
  if (!reuseSelection.checked) {
    lockedSelectionNormalized = null;
    clearSelectionButton.disabled = true;
  } else if (selectionNormalized) {
    lockedSelectionNormalized = [...selectionNormalized];
    clearSelectionButton.disabled = false;
  }
});
clearSelectionButton.addEventListener('click', () => {
  lockedSelectionNormalized = null;
  clearSelectionButton.disabled = true;
  instruction.textContent = 'Saved text selection cleared. The next captured frame will need a new selection.';
});

for (const field of [setCode, cardNumber, setTotal]) {
  field.addEventListener('input', resetLookup);
}

async function lookupCurrentCard() {
  lookupButton.disabled = true;
  lookupState.textContent = 'CHECKING';
  lookupState.className = 'state';
  lookupResult.hidden = true;
  lookupMessage.textContent = 'Checking the local Malie catalog...';
  try {
    const response = await fetch('/lookup', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        set_code: setCode.value,
        card_number: cardNumber.value,
        set_total: setTotal.value,
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Lookup failed');
    const card = result.card || {};
    if (!card.card_name) {
      lastLookupStatus = card.status === 'review' ? 'review' : 'no_match';
      lookupState.textContent = lastLookupStatus === 'review' ? 'REVIEW' : 'NO MATCH';
      lookupState.className = 'state bad';
      lookupMessage.textContent = 'No exact local card was found. Check the set code and card number; nothing was added.';
      instruction.textContent = lastLookupStatus === 'review'
        ? 'Review the entered identifiers; the local catalog did not produce one unique card.'
        : 'No exact match was found. Correct the editable fields, then press Find this card.';
      return;
    }
    lastLookupStatus = card.status === 'accepted' ? 'accepted' : 'review';
    lookupState.textContent = card.status === 'accepted' ? 'EXACT MATCH' : 'REVIEW';
    lookupState.className = `state ${card.status === 'accepted' ? 'good' : 'bad'}`;
    lookupName.textContent = card.card_name;
    lookupIdentity.textContent = `${card.set_name || card.set_code} — ${card.set_code} ${card.card_number}${card.printed_total ? `/${card.printed_total}` : ''}`;
    lookupSource.textContent = `Source: ${card.source || 'catalog'}`;
    lookupResult.hidden = false;
    if (card.image_url) {
      lookupImage.src = card.image_url;
      lookupImage.alt = `${card.card_name} card image`;
      lookupImage.hidden = false;
    }
    lookupMessage.textContent = card.review_reasons?.length
      ? `Review required: ${card.review_reasons.join('; ')}. Nothing was added.`
      : 'Exact set-and-number match. Compare the name and image to the physical card. Nothing was added.';
    if (lastLookupStatus === 'accepted') {
      lookupButton.hidden = true;
      inventoryQuantity.textContent = String(result.inventory_quantity ?? 0);
      addInventoryButton.disabled = false;
      inventoryMessage.textContent = 'Exact match confirmed. Choose how many copies to add.';
      instruction.textContent = 'Exact visual match found. No corrections are needed; save the OCR reading, then press Next card.';
      message.textContent = 'The database has the canonical card information. Leave the editable boxes alone unless the displayed card is wrong.';
    } else {
      lookupButton.hidden = false;
      instruction.textContent = 'Review the displayed card and correct a field only if the identity or printed total is wrong.';
    }
  } catch (error) {
    lookupState.textContent = 'LOOKUP ERROR';
    lookupState.className = 'state bad';
    lookupMessage.textContent = `${error.message}. Your OCR result is still safe and can be saved.`;
  } finally {
    updateLookupAvailability();
  }
}

lookupButton.addEventListener('click', () => void lookupCurrentCard());

addInventoryButton.addEventListener('click', async () => {
  if (lastLookupStatus !== 'accepted') return;
  const quantityToAdd = Number(inventoryAddQuantity.value);
  if (!Number.isInteger(quantityToAdd) || quantityToAdd < 1 || quantityToAdd > 99) {
    inventoryMessage.textContent = 'Enter a whole-number quantity from 1 to 99.';
    return;
  }
  addInventoryButton.disabled = true;
  undoInventoryButton.disabled = true;
  inventoryMessage.textContent = `Rechecking the exact match and adding ${quantityToAdd} ${quantityToAdd === 1 ? 'copy' : 'copies'}...`;
  try {
    const response = await fetch('/inventory/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        set_code: setCode.value,
        card_number: cardNumber.value,
        set_total: setTotal.value,
        scan_id: scanId,
        quantity: quantityToAdd,
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Inventory addition failed');
    currentInventoryEventId = Number(result.inventory?.event_id || 0);
    inventoryQuantity.textContent = String(result.inventory?.quantity ?? 0);
    inventoryAddQuantity.value = '1';
    undoInventoryButton.disabled = !currentInventoryEventId;
    const added = Number(result.inventory?.quantity_delta || quantityToAdd);
    inventoryMessage.textContent = `Added ${added} ${added === 1 ? 'copy' : 'copies'} of ${result.card?.card_name || 'this card'}. The batch was saved locally.`;
  } catch (error) {
    inventoryMessage.textContent = error.message;
  } finally {
    addInventoryButton.disabled = lastLookupStatus !== 'accepted';
  }
});

undoInventoryButton.addEventListener('click', async () => {
  if (!currentInventoryEventId) return;
  undoInventoryButton.disabled = true;
  addInventoryButton.disabled = true;
  inventoryMessage.textContent = 'Undoing the last batch...';
  try {
    const response = await fetch('/inventory/undo', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({event_id: currentInventoryEventId}),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Inventory undo failed');
    inventoryQuantity.textContent = String(result.inventory?.quantity ?? 0);
    const undone = Math.abs(Number(result.inventory?.quantity_delta || 0));
    currentInventoryEventId = 0;
    inventoryMessage.textContent = `The last batch${undone ? ` of ${undone}` : ''} was undone. The history remains recorded.`;
  } catch (error) {
    inventoryMessage.textContent = error.message;
  } finally {
    addInventoryButton.disabled = lastLookupStatus !== 'accepted';
  }
});

saveButton.addEventListener('click', async () => {
  const payload = {
    iteration: UI_ITERATION,
    scan_id: scanId,
    corrected_letters: [regulationMark.value, setCode.value].filter(Boolean).join(' '),
    corrected_numbers: [cardNumber.value, setTotal.value].filter(Boolean).join(' / '),
  };
  saveButton.disabled = true;
  try {
    const response = await fetch('/save', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Save failed');
    state.textContent = 'SAVED';
    state.className = 'state good';
    scanId = '';
    message.textContent = capturedFromCamera
      ? 'Saved this labeled example. Press Next card when the slot is ready.'
      : 'Saved this labeled example to the current iteration CSV.';
  } catch (error) {
    state.textContent = 'SAVE ERROR';
    state.className = 'state bad';
    message.textContent = error.message;
    saveButton.disabled = false;
  }
});

window.addEventListener('resize', () => {
  fitImage();
  sizeCameraFrame();
});
window.addEventListener('pagehide', stopMediaTracks);
window.addEventListener('beforeunload', stopMediaTracks);
void verifyVersion();
