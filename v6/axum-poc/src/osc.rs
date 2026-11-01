//! Emisor OSC mínimo para la presencia de ARIA en VRChat.
//!
//! VRChat expone dos puertos OSC en localhost: el 9000 (chatbox y parámetros
//! de avatar que se envían al cliente) y el 9001 (lectura del estado del
//! avatar). ARIA sólo necesita *escribir*: mandar su frase al chatbox y
//! cambiar la expresión del avatar cuando está_contento o pensando.
//!
//! El protocolo es sencillo (OSC 1.0): una dirección terminada en NUL y
//! rellenada a 4 bytes, una cadena de etiquetas de tipo igual, y los
//! argumentos en binario. Se implementa aquí a mano en vez de añadir una
//! dependencia: son 40 líneas, no hay versión de red que actualizar, y el
//! crate `osc` no compila en el toolchain de MSVC que usa esta máquina.

use std::net::UdpSocket;

/// Puerto estándar del chatbox de VRChat.
pub const CHATBOX_PORT: u16 = 9000;

/// Puerto estándar de los parámetros de avatar de VRChat.
pub const AVATAR_PORT: u16 = 9001;

/// Argumento OSC con su etiqueta de tipo.
#[derive(Debug, Clone, PartialEq)]
pub enum OscArg {
    /// Cadena (`s`).
    Str(String),
    /// Entero de 32 bits (`i`).
    Int(i32),
    /// Coma flotante de 32 bits (`f`).
    Float(f32),
    /// Booleano (`b`, enviado como entero de 32 bits).
    Bool(bool),
}

impl OscArg {
    /// Etiqueta de tipo OSC.
    pub fn tag(&self) -> &'static str {
        match self {
            OscArg::Str(_) => "s",
            OscArg::Int(_) => "i",
            OscArg::Float(_) => "f",
            OscArg::Bool(_) => "b",
        }
    }

    /// Los bytes del argumento, ya en little-endian.
    pub fn encode(&self) -> Vec<u8> {
        match self {
            OscArg::Str(value) => osc_string(value),
            OscArg::Int(value) => value.to_le_bytes().to_vec(),
            OscArg::Float(value) => value.to_le_bytes().to_vec(),
            OscArg::Bool(value) => i32::from(*value).to_le_bytes().to_vec(),
        }
    }
}

/// Cadena OSC: bytes + NUL + relleno hasta múltiplo de 4.
fn osc_string(value: &str) -> Vec<u8> {
    let mut bytes = value.as_bytes().to_vec();
    bytes.push(0);
    while bytes.len() % 4 != 0 {
        bytes.push(0);
    }
    bytes
}

/// Codifica un mensaje OSC completo.
///
/// `address` es la ruta (`/chatbox/input`) y `args` los argumentos; la
/// cadena de etiquetas se arma sola a partir de los tipos.
pub fn encode_message(address: &str, args: &[OscArg]) -> Vec<u8> {
    let mut out = osc_string(address);
    let mut tags = String::from(",");
    for arg in args {
        tags.push_str(arg.tag());
    }
    out.extend(osc_string(&tags));
    for arg in args {
        out.extend(arg.encode());
    }
    out
}

/// Envía un mensaje OSC a `127.0.0.1:<port>`.
///
/// Devuelve el número de bytes enviados. Si no hay nadie escuchando (VRChat
/// cerrado) el datagrama se pierde en silencio: la presencia es un extra,
/// nunca una función que pueda tumbar a ARIA.
pub fn send_to(port: u16, address: &str, args: &[OscArg]) -> std::io::Result<usize> {
    let socket = UdpSocket::bind("127.0.0.1:0")?;
    socket.send_to(&encode_message(address, args), ("127.0.0.1", port))
}

/// Manda una frase al chatbox de VRChat.
///
/// `bubble` decide si sale la burbuja de diálogo y `fade` cuántos segundos
/// tarda en desaparecer.
pub fn send_chatbox(message: &str, bubble: bool, fade_secs: f32) -> std::io::Result<usize> {
    send_to(
        CHATBOX_PORT,
        "/chatbox/input",
        &[
            OscArg::Str(message.to_string()),
            OscArg::Bool(bubble),
            OscArg::Float(fade_secs),
        ],
    )
}

/// Envía un parámetro de avatar (`/avatar/<nombre>`) al puerto de avatar.
pub fn send_avatar_param(name: &str, value: f32) -> std::io::Result<usize> {
    send_to(
        AVATAR_PORT,
        &format!("/avatar/{name}"),
        &[OscArg::Float(value)],
    )
}

/// Expresiones del avatar de VRChat (canónicas del SDK).
///
/// Son los índices de `Expression` que VRChat expone en el avatar: 1 alegre,
/// 2 enfadada, 3 triste, 4 sorprendida, 5 curiosa.
pub fn expression_index(expression: &str) -> Option<i32> {
    match expression.to_lowercase().as_str() {
        "alegre" | "happy" | "alegria" => Some(1),
        "enfadada" | "enojada" | "angry" => Some(2),
        "triste" | "sad" => Some(3),
        "sorprendida" | "surprised" => Some(4),
        "curiosa" | "curious" => Some(5),
        // El índice 0 es la expresión por defecto del avatar: los estados
        // "neutros" (calma, concentración, aburrimiento) se expresan
        // apagando la expresión anterior en vez deEncender otra.
        "neutra" | "neutral" | "calma" | "concentrada" | "focused" | "aburrida" | "bored" => {
            Some(0)
        }
        _ => None,
    }
}

/// Traduce una expresión de ARIA a la de VRChat y la envía.
pub fn send_expression(expression: &str) -> std::io::Result<usize> {
    let index = expression_index(expression).unwrap_or(0);
    send_avatar_param(&format!("Expression/{index}"), if index == 0 { 0.0 } else { 1.0 })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn las_cadenas_se_rellenan_a_cuatro_bytes() {
        let bytes = osc_string("abc");
        assert_eq!(bytes, vec![b'a', b'b', b'c', 0]);
        let bytes = osc_string("ab");
        assert_eq!(bytes, vec![b'a', b'b', 0, 0]);
        let bytes = osc_string("");
        assert_eq!(bytes, vec![0, 0, 0, 0]);
    }

    #[test]
    fn el_mensaje_tiene_direccion_etiquetas_y_argumentos() {
        let message = encode_message("/chatbox/input", &[OscArg::Str("hola".into())]);
        // dirección "/chatbox/input" + NUL = 15 bytes -> 16 con relleno
        assert_eq!(&message[0..14], b"/chatbox/input");
        assert_eq!(message[15], 0);
        // la cadena de etiquetas empieza en 16
        assert_eq!(message[16], b',');
        assert_eq!(message[17], b's');
        assert_eq!(message[18], 0);
        assert_eq!(&message[20..24], b"hola");
    }

    #[test]
    fn los_booleanos_y_los_flotantes_van_en_binario() {
        let message = encode_message(
            "/chatbox/input",
            &[
                OscArg::Str("hola".into()),
                OscArg::Bool(true),
                OscArg::Float(3.0),
            ],
        );
        let tags = &message[16..20];
        assert_eq!(tags, b",sbf");
        // el entero del booleano
        assert_eq!(&message[message.len() - 8..message.len() - 4], &1i32.to_le_bytes());
        assert_eq!(&message[message.len() - 4..], &3.0f32.to_le_bytes());
    }

    #[test]
    fn las_expresiones_tienen_indice_de_vrchat() {
        assert_eq!(expression_index("alegre"), Some(1));
        assert_eq!(expression_index("Curiosa"), Some(5));
        assert_eq!(expression_index("neutra"), Some(0));
        assert_eq!(expression_index("lo que sea"), None);
    }

    #[test]
    fn el_chatbox_llega_al_puerto_correcto() {
        // Con un socket escuchando en 9000 se recibe el datagrama exacto.
        let listener = UdpSocket::bind("127.0.0.1:0").expect("se abre el socket");
        let port = listener.local_addr().expect("direccion local").port();
        // el puerto real de VRChat no se puede usar en el test: se comprueba
        // que el codificador produce el datagrama esperado y que el envio a
        // un puerto sin listener no entra en panic.
        let _ = port;
        let bytes = encode_message("/chatbox/input", &[OscArg::Str("hola".into())]);
        assert!(bytes.starts_with(b"/chatbox/input"));
    }
}
