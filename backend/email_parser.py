import base64
from bs4 import BeautifulSoup
import re
import html


def clean_email_text(text: str) -> str:
    #Decode HTML entities
    text = html.unescape(text)

    #Remove URLs
    text = re.sub(
        r"https?://[^\s<>]+",
        "[LINK]",
        text
    )

    #Normalize carriage returns and newlines
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    #Replace tabs with spaces
    text = text.replace("\t", " ")

    #Remove invisible formatting characters
    text = re.sub(
        r"[\u200b-\u200f\u2060\ufeff\u00ad]",
        "",
        text
    )

    #Collapse repeated horizontal whitespace
    text = re.sub(r"[^\S\n]+", " ", text)

    #Remove spaces around newlines
    text = re.sub(r" *\n *", "\n", text)

    #Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()    # Decode HTML entities like &amp; and &#39;
    

def decode_body(data: str) -> str:
    if not data:
        return ""
    # Gmail uses URL-safe Base64
    decoded_bytes = base64.urlsafe_b64decode(data)
    return decoded_bytes.decode("utf-8", errors="replace")

def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts, styles and other non-content elements
    for tag in soup(["script", "style", "head"]):
        tag.decompose()

    return soup.get_text(separator=" ", strip=True)

def extract_email_body(payload: dict) -> str:
    plain_parts = []
    html_parts = []

    def walk(part):
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")

        # Ignore attachments
        if part.get("filename"):
            return

        if data and mime_type == "text/plain":
            plain_parts.append(decode_body(data))

        elif data and mime_type == "text/html":
            html_parts.append(
                html_to_text(decode_body(data))
            )

        # Multipart emails contain nested components
        for child in part.get("parts", []):
            walk(child)

    walk(payload)

    if plain_parts:
        return "\n".join(plain_parts).strip()

    return "\n".join(html_parts).strip()