#!/usr/bin/env node

// AIS Message Decoder
// Decodes NMEA AIS messages to show ship position and status data

function sixBitToChar(val) {
    // AIS 6-bit ASCII encoding
    if (val < 40) {
        return String.fromCharCode(val + 48);
    } else {
        return String.fromCharCode(val + 56);
    }
}

function charToSixBit(char) {
    const code = char.charCodeAt(0);
    if (code >= 48 && code < 88) {
        return code - 48;
    } else if (code >= 96 && code < 128) {
        return code - 56;
    }
    return 0;
}

function payloadToBitstring(payload) {
    let bitstring = '';
    for (let i = 0; i < payload.length; i++) {
        const val = charToSixBit(payload[i]);
        bitstring += val.toString(2).padStart(6, '0');
    }
    return bitstring;
}

function extractBits(bitstring, start, length) {
    return bitstring.substr(start, length);
}

function bitsToUnsigned(bits) {
    return parseInt(bits, 2);
}

function bitsToSigned(bits) {
    const value = parseInt(bits, 2);
    const signBit = 1 << (bits.length - 1);
    return (value & signBit) ? value - (1 << bits.length) : value;
}

function decodeAISMessage(nmea) {
    console.log(`\n=== Decoding: ${nmea} ===`);
    
    // Parse NMEA sentence
    const parts = nmea.split(',');
    if (parts.length < 6) {
        console.log('Invalid NMEA sentence');
        return null;
    }
    
    const payload = parts[5];
    const checksum = nmea.split('*')[1];
    
    console.log(`Payload: ${payload}`);
    console.log(`Checksum: ${checksum}`);
    
    // Convert payload to bitstring
    const bitstring = payloadToBitstring(payload);
    console.log(`Bitstring: ${bitstring} (${bitstring.length} bits)`);
    
    // Extract AIS fields
    let pos = 0;
    
    const msgType = bitsToUnsigned(extractBits(bitstring, pos, 6)); pos += 6;
    const repeat = bitsToUnsigned(extractBits(bitstring, pos, 2)); pos += 2;
    const mmsi = bitsToUnsigned(extractBits(bitstring, pos, 30)); pos += 30;
    const navStatus = bitsToUnsigned(extractBits(bitstring, pos, 4)); pos += 4;
    const rot = bitsToSigned(extractBits(bitstring, pos, 8)) - 128; pos += 8;
    const sog = bitsToUnsigned(extractBits(bitstring, pos, 10)) / 10; pos += 10;
    const accuracy = bitsToUnsigned(extractBits(bitstring, pos, 1)); pos += 1;
    const lon = bitsToSigned(extractBits(bitstring, pos, 28)) / 600000; pos += 28;
    const lat = bitsToSigned(extractBits(bitstring, pos, 27)) / 600000; pos += 27;
    const cog = bitsToUnsigned(extractBits(bitstring, pos, 12)) / 10; pos += 12;
    const hdg = bitsToUnsigned(extractBits(bitstring, pos, 9)); pos += 9;
    const timestamp = bitsToUnsigned(extractBits(bitstring, pos, 6)); pos += 6;
    
    const navStatusNames = {
        0: 'Under way using engine',
        1: 'At anchor',
        2: 'Not under command',
        3: 'Restricted manoeuvrability',
        4: 'Constrained by her draught',
        5: 'Moored',
        6: 'Aground',
        7: 'Engaged in fishing',
        8: 'Under way sailing',
        9: 'Reserved',
        10: 'Reserved',
        11: 'Reserved',
        12: 'Reserved',
        13: 'Reserved',
        14: 'AIS-SART',
        15: 'Undefined'
    };
    
    console.log(`\nDECODED AIS MESSAGE:`);
    console.log(`Message Type: ${msgType}`);
    console.log(`Repeat: ${repeat}`);
    console.log(`MMSI: ${mmsi}`);
    console.log(`Navigation Status: ${navStatus} (${navStatusNames[navStatus] || 'Unknown'})`);
    console.log(`Rate of Turn: ${rot} degrees/min`);
    console.log(`Speed over Ground: ${sog} knots`);
    console.log(`Position Accuracy: ${accuracy} (${accuracy ? 'High' : 'Low'})`);
    console.log(`Longitude: ${lon.toFixed(6)}°`);
    console.log(`Latitude: ${lat.toFixed(6)}°`);
    console.log(`Course over Ground: ${cog.toFixed(1)}°`);
    console.log(`True Heading: ${hdg}°`);
    console.log(`Timestamp: ${timestamp} seconds`);
    
    // Validation checks
    const issues = [];
    if (lat < -90 || lat > 90) issues.push(`Invalid latitude: ${lat}`);
    if (lon < -180 || lon > 180) issues.push(`Invalid longitude: ${lon}`);
    if (sog < 0 || sog > 102.2) issues.push(`Invalid speed: ${sog} knots`);
    if (cog < 0 || cog >= 360) issues.push(`Invalid course: ${cog}°`);
    if (hdg < 0 || hdg >= 360) issues.push(`Invalid heading: ${hdg}°`);
    if (mmsi < 100000000 || mmsi > 999999999) issues.push(`Invalid MMSI: ${mmsi}`);
    
    if (issues.length > 0) {
        console.log(`\nVALIDATION ISSUES:`);
        issues.forEach(issue => console.log(`- ${issue}`));
    } else {
        console.log(`\nVALIDATION: All fields are valid ✓`);
    }
    
    return {
        msgType, repeat, mmsi, navStatus, rot, sog, accuracy,
        lon, lat, cog, hdg, timestamp, valid: issues.length === 0
    };
}

// Messages to decode
const messages = [
    '!AIVDM,1,1,,A,1;4uD@1wFDAlF832mH000000,0*5A',
    '!AIVDM,1,1,,A,1>Dcw3@P1TwFPcDFVR83Q2lr000000,0*4D',
    '!AIVDM,1,1,,A,1>Dcw3@1wFHedF832mn00000,0*0F',
    '!AIVDM,1,1,,A,1>Dcw3@P1TwFPfdFVR83Q2m0000000,0*2B',
    '!AIVDM,1,1,,A,1>Dcw3@1wFHi4F832l400000,0*08'
];

console.log('AIS Message Decoder');
console.log('===================');

messages.forEach((msg, i) => {
    console.log(`\n--- Message ${i + 1} ---`);
    decodeAISMessage(msg);
});

console.log('\n\nSUMMARY:');
console.log('========');
messages.forEach((msg, i) => {
    const decoded = decodeAISMessage(msg);
    if (decoded) {
        console.log(`Message ${i + 1}: MMSI ${decoded.mmsi}, ${decoded.lat.toFixed(6)}°, ${decoded.lon.toFixed(6)}°, ${decoded.cog.toFixed(1)}°, ${decoded.sog} kts`);
    }
});
