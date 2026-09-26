/**
 * AURA Three.js Post-Processing Effects
 * Librería de efectos visuales para Three.js
 * Incluye: UnrealBloomPass, GlitchPass, y otros efectos de producción
 * Optimizado para integración con el sistema AURA
 */

// Exportar clases para uso global
export { EffectComposer, RenderPass, ShaderPass, UnrealBloomPass, GlitchPass };

/**
 * EffectComposer - Composer para post-procesamiento
 */
class EffectComposer {
    constructor(renderer, renderTarget) {
        this.renderer = renderer;
        this.renderTarget = renderTarget || new THREE.WebGLRenderTarget(renderer.domElement.width, renderer.domElement.height, {
            minFilter: THREE.LinearFilter,
            magFilter: THREE.LinearFilter,
            format: THREE.RGBAFormat,
            stencilBuffer: false
        });

        this.passes = [];
        this.copyPass = new ShaderPass(THREE.CopyShader);
        this.copyPass.renderToScreen = true;
        this.passes.push(this.copyPass);

        this._size = {
            width: renderer.domElement.width,
            height: renderer.domElement.height
        };

        this._pixelRatio = renderer.getPixelRatio();
        this._stereo = false;
    }

    addPass(pass) {
        this.passes.push(pass);
        pass.setSize(this._size.width, this._size.height);
        return this;
    }

    removePass(pass) {
        const index = this.passes.indexOf(pass);
        if (index !== -1) {
            this.passes.splice(index, 1);
        }
        return this;
    }

    render() {
        if (this.renderTarget) {
            this.renderer.setRenderTarget(this.renderTarget);
            this.renderer.clear();
        }

        for (let i = 0, il = this.passes.length; i < il; i++) {
            this.passes[i].render(this.renderer, this.renderTarget, this._size.width, this._size.height);
        }

        if (this.renderTarget) {
            this.renderer.setRenderTarget(null);
        }
    }

    setSize(width, height) {
        this._size.width = width;
        this._size.height = height;

        for (let i = 0, il = this.passes.length; i < il; i++) {
            this.passes[i].setSize(width, height);
        }
    }

    swapToMainRenderTarget() {
        this.renderer.setRenderTarget(this.renderTarget);
    }

    swapFromMainRenderTarget() {
        this.renderer.setRenderTarget(null);
    }
}

/**
 * RenderPass - Pasa de renderizado básico
 */
class RenderPass {
    constructor(scene, camera, overrideMaterial, clearColor, clearAlpha) {
        this.scene = scene;
        this.camera = camera;
        this.overrideMaterial = overrideMaterial;
        this.clearColor = clearColor;
        this.clearAlpha = clearAlpha !== undefined ? clearAlpha : 0;
        this.needsSwap = true;
    }

    render(renderer, writeBuffer, readBuffer, deltaTime) {
        const oldAutoClear = renderer.autoClear;
        renderer.autoClear = false;

        renderer.setRenderTarget(readBuffer);
        renderer.clear();
        renderer.clearColor();
        renderer.clearDepth();
        renderer.clearStencil();

        if (this.clearColor) {
            renderer.setClearColor(this.clearColor);
        }

        if (this.clearAlpha !== undefined) {
            renderer.setClearAlpha(this.clearAlpha);
        }

        if (this.overrideMaterial !== undefined) {
            this.scene.overrideMaterial = this.overrideMaterial;
        }

        renderer.render(this.scene, this.camera);

        if (this.overrideMaterial !== undefined) {
            this.scene.overrideMaterial = undefined;
        }

        renderer.setRenderTarget(writeBuffer);
        if (this.needsSwap) {
            renderer.copyFramebufferToTexture(readBuffer);
            if (oldAutoClear !== true) {
                renderer.clear();
            }
        }
    }

    setSize(width, height) {
        // No se requiere implementación para RenderPass
    }
}

/**
 * ShaderPass - Pasa de shader personalizado
 */
class ShaderPass {
    constructor(shader, textureID) {
        this.textureID = (textureID !== undefined) ? textureID : 'tDiffuse';
        this.uniforms = THREE.UniformsUtils.clone(shader.uniforms);

        this.material = new THREE.ShaderMaterial({
            uniforms: this.uniforms,
            vertexShader: shader.vertexShader,
            fragmentShader: shader.fragmentShader
        });

        this.renderTargetParameters = {
            minFilter: THREE.LinearFilter,
            magFilter: THREE.LinearFilter,
            format: THREE.RGBAFormat,
            stencilBuffer: false
        };

        this.renderTarget = new THREE.WebGLRenderTarget(window.innerWidth, window.innerHeight, this.renderTargetParameters);
        this.needsSwap = true;
    }

    render(renderer, writeBuffer, readBuffer, deltaTime) {
        if (this.uniforms[this.textureID]) {
            this.uniforms[this.textureID].value = readBuffer.texture;
        }

        renderer.render(this.scene, this.camera, this.renderTarget, this.forceClear);
    }

    setSize(width, height) {
        if (this.renderTarget) {
            this.renderTarget.setSize(width, height);
        }
    }
}

/**
 * UnrealBloomPass - Efecto de brillo (Bloom)
 */
class UnrealBloomPass {
    constructor(resolution, strength, radius, threshold) {
        this.resolution = (resolution !== undefined) ? new THREE.Vector2(resolution) : new THREE.Vector2(256, 256);
        this.strength = (strength !== undefined) ? strength : 1.0;
        this.radius = (radius !== undefined) ? radius : 0.0005;
        this.threshold = (threshold !== undefined) ? threshold : 0.0;
        this.nMips = 5;

        this.operateBuffer1 = new THREE.WebGLRenderTarget(this.resolution.x, this.resolution.y);
        this.operateBuffer2 = new THREE.WebGLRenderTarget(this.resolution.x, this.resolution.y);
        this.finalBuffer = null;

        this.bloomIntensity = 1.0;
        this.bloomStrength = 1.0;
        this.bloomRadius = 0.5;

        this.setupShaderMaterial();
    }

    setupShaderMaterial() {
        this.uniforms = {
            'tDiffuse': { value: null },
            'size': { value: new THREE.Vector2(0, 0) },
            'radius': { value: 0.8 },
            'power': { value: 4.0 }
        };

        this.materialBloom = new THREE.ShaderMaterial({
            uniforms: this.uniforms,
            vertexShader: `
                varying vec2 vUv;
                void main() {
                    vUv = uv;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform sampler2D tDiffuse;
                uniform vec2 size;
                uniform float radius;
                uniform float power;

                varying vec2 vUv;

                void main() {
                    vec4 color = vec4(0.0);
                    vec2 delta = size * radius;
                    vec2 uv = vUv;

                    color += texture2D(tDiffuse, uv) * 0.16;
                    color += texture2D(tDiffuse, uv + delta) * 0.08;
                    color += texture2D(tDiffuse, uv - delta) * 0.08;
                    color += texture2D(tDiffuse, uv + delta.yx) * 0.08;
                    color += texture2D(tDiffuse, uv - delta.yx) * 0.08;

                    color += texture2D(tDiffuse, uv + delta * 1.3) * 0.04;
                    color += texture2D(tDiffuse, uv - delta * 1.3) * 0.04;
                    color += texture2D(tDiffuse, uv + delta.yx * 1.3) * 0.04;
                    color += texture2D(tDiffuse, uv - delta.yx * 1.3) * 0.04;

                    gl_FragColor = pow(color, vec4(power));
                }
            `,
            defines: {}
        });

        this.materialBloom.uniforms['size'].value = this.resolution;
    }

    render(renderer, writeBuffer, readBuffer, deltaTime) {
        if (this.finalBuffer === null) {
            this.finalBuffer = readBuffer.clone();
        }

        // Renderizar a buffers de operación
        renderer.setRenderTarget(this.operateBuffer1);
        renderer.render(readBuffer.scene, readBuffer.camera);

        // Aplicar efecto de bloom
        renderer.setRenderTarget(this.operateBuffer2);
        this.materialBloom.uniforms['tDiffuse'].value = this.operateBuffer1.texture;
        this.materialBloom.uniforms['size'].value.set(this.resolution.x, this.resolution.y);
        renderer.render(new THREE.Scene(), new THREE.Camera());

        // Mezclar con el buffer original
        renderer.setRenderTarget(writeBuffer);
        renderer.render(readBuffer.scene, readBuffer.camera);

        // Aplicar el bloom final
        this.materialBloom.uniforms['tDiffuse'].value = this.operateBuffer2.texture;
        this.materialBloom.uniforms['size'].value.set(this.resolution.x, this.resolution.y);
        renderer.render(new THREE.Scene(), new THREE.Camera());
    }

    setSize(width, height) {
        this.resolution.set(width, height);
        this.operateBuffer1.setSize(width, height);
        this.operateBuffer2.setSize(width, height);
        this.materialBloom.uniforms['size'].value.set(width, height);
    }
}

/**
 * GlitchPass - Efecto de distorsión digital (Glitch)
 */
class GlitchPass {
    constructor() {
        this.enabled = true;
        this.goWild = false;
        this.curF = 0;
        this.curF2 = 0;
        this.curF3 = 0;
        this.tDx = 0;
        this.tDy = 0;
        this.sDx = 0;
        this.sDy = 0;
        this.dx = [0, 0, 0];
        this.dy = [0, 0, 0];

        this.uniforms = {
            'tDiffuse': { value: null },
            'tSize': { value: new THREE.Vector2(0, 0) },
            'tMap': { value: null },
            'tMapSize': { value: new THREE.Vector2(0, 0) },
            'seed': { value: 0.0 },
            'bypass': { value: 0.0 },
            'power': { value: 0.0 },
            'amount': { value: 0.07 }
        };

        this.setupShaderMaterial();
    }

    setupShaderMaterial() {
        this.material = new THREE.ShaderMaterial({
            uniforms: this.uniforms,
            vertexShader: `
                varying vec2 vUv;
                void main() {
                    vUv = uv;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform sampler2D tDiffuse;
                uniform sampler2D tMap;
                uniform vec2 tSize;
                uniform vec2 tMapSize;
                uniform float seed;
                uniform float bypass;
                uniform float power;
                uniform float amount;

                varying vec2 vUv;

                void main() {
                    if (bypass > 0.5) {
                        gl_FragColor = texture2D(tDiffuse, vUv);
                        return;
                    }

                    vec4 color = texture2D(tDiffuse, vUv);

                    // Glitch effect
                    vec2 uv = vUv;
                    vec2 newUv = uv;

                    // Random displacement
                    float rand = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453 + seed);
                    float r1 = rand * 2.0 - 1.0;
                    float r2 = rand * 2.0 - 1.0;
                    float r3 = rand * 2.0 - 1.0;
                    float r4 = rand * 2.0 - 1.0;

                    // Apply displacement
                    if (goWild == 1.0) {
                        newUv.x += r1 * amount * 0.01;
                        newUv.y += r2 * amount * 0.01;
                    } else {
                        newUv.x += r1 * amount * 0.005;
                        newUv.y += r2 * amount * 0.005;
                    }

                    // Scanlines
                    float scanline = sin(uv.y * tSize.y * 10.0) * 0.01;
                    color.r += scanline * 0.01;
                    color.g += scanline * 0.01;
                    color.b += scanline * 0.01;

                    // Color shift
                    color.r += r3 * 0.01;
                    color.g += r4 * 0.01;

                    gl_FragColor = color;
                }
            `,
            defines: {
                'goWild': '0.0'
            }
        });
    }

    render(renderer, writeBuffer, readBuffer, deltaTime) {
        if (!this.enabled) {
            renderer.copyFramebufferToTexture(readBuffer);
            return;
        }

        this.curF += deltaTime;
        this.curF3 += deltaTime * 0.5;

        if (this.curF > 25000.0) {
            this.curF = 0.0;
        }

        if (this.curF3 > 25000.0) {
            this.curF3 = 0.0;
        }

        this.uniforms['tDiffuse'].value = readBuffer.texture;
        this.uniforms['tSize'].value.set(readBuffer.width, readBuffer.height);
        this.uniforms['seed'].value = this.curF * 0.00001;
        this.uniforms['bypass'].value = this.enabled ? 0.0 : 1.0;
        this.uniforms['power'].value = this.goWild ? 0.3 : 0.0;
        this.uniforms['amount'].value = this.goWild ? 0.07 : 0.03;

        renderer.render(new THREE.Scene(), new THREE.Camera(), writeBuffer, true);
    }

    setSize(width, height) {
        this.uniforms['tSize'].value.set(width, height);
    }
}

// Shader para corrección de gamma
const GammaCorrectionShader = {
    uniforms: {
        "tDiffuse": { value: null },
        "power": { value: 2.2 },
        "invGamma": { value: 1.0 / 2.2 }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform float power;
        uniform float invGamma;

        varying vec2 vUv;

        void main() {
            vec4 linearColor = texture2D(tDiffuse, vUv);
            gl_FragColor = vec4(pow(linearColor.rgb, vec3(invGamma)), linearColor.a);
        }
    `
};

// Shader para FXAA (Anti-Aliasing)
const FXAAShader = {
    uniforms: {
        "tDiffuse": { value: null },
        "resolution": { value: new THREE.Vector2(1 / 1024, 1 / 512) }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform vec2 resolution;

        varying vec2 vUv;

        void main() {
            vec3 rgbNW = texture2D(tDiffuse, (gl_FragCoord.xy + vec2(-1.0, -1.0)) * resolution).xyz;
            vec3 rgbNE = texture2D(tDiffuse, (gl_FragCoord.xy + vec2(1.0, -1.0)) * resolution).xyz;
            vec3 rgbSW = texture2D(tDiffuse, (gl_FragCoord.xy + vec2(-1.0, 1.0)) * resolution).xyz;
            vec3 rgbSE = texture2D(tDiffuse, (gl_FragCoord.xy + vec2(1.0, 1.0)) * resolution).xyz;
            vec3 rgbM  = texture2D(tDiffuse, gl_FragCoord.xy * resolution).xyz;

            vec3 luma = vec3(0.299, 0.587, 0.114);
            float lumaNW = dot(rgbNW, luma);
            float lumaNE = dot(rgbNE, luma);
            float lumaSW = dot(rgbSW, luma);
            float lumaSE = dot(rgbSE, luma);
            float lumaM  = dot(rgbM, luma);
            float lumaMin = min(min(min(lumaNW, lumaNE), lumaSW), lumaSE);
            float lumaMax = max(max(max(lumaNW, lumaNE), lumaSW), lumaSE);

            vec2 dir;
            dir.x = -((lumaM - lumaNW) + (lumaM - lumaNE));
            dir.y = -((lumaM - lumaSW) + (lumaM - lumaSE));

            float dirReduce = max((lumaM - lumaMin), (lumaMax - lumaM));
            float lumaReducedM = mix(lumaMin, lumaMax, 0.5);
            float lumaReducedA = mix(lumaM, lumaReducedM, 0.5);
            float lumaReducedB = lumaM - dirReduce;

            vec2 uvOffset = vec2(0.0);
            uvOffset += vec2(0.5) * dir * (1.0 / 0.5 + 2.0) / resolution.xy;
            uvOffset += vec2(0.5) * dir * (1.0 / 0.5 - 2.0) / resolution.xy;

            vec3 rgbA = texture2D(tDiffuse, vUv + uvOffset * (1.0 / 3.0 - 0.5)).xyz;
            vec3 rgbB = texture2D(tDiffuse, vUv + uvOffset * (2.0 / 3.0 - 0.5)).xyz;

            float lumaA = dot(rgbA, luma);
            float lumaB = dot(rgbB, luma);

            float lumaEnd = mix(lumaA, lumaB, step(lumaReducedB, lumaReducedA));

            gl_FragColor = vec4(mix(rgbA, rgbB, step(lumaReducedB, lumaReducedA)), 1.0);
        }
    `
};

// Shader para copia de framebuffer
const CopyShader = {
    uniforms: {
        "tDiffuse": { value: null },
        "opacity": { value: 1.0 }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform float opacity;

        varying vec2 vUv;

        void main() {
            vec4 texel = texture2D(tDiffuse, vUv);
            gl_FragColor = vec4(texel.rgb, texel.a * opacity);
        }
    `
};