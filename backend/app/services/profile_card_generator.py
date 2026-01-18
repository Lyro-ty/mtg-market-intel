"""
Profile Card PNG Generator Service.

Generates trading card-style PNG images of user profiles for social sharing.
"""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import Optional


FRAME_COLORS = {
    "bronze": "#CD7F32",
    "silver": "#C0C0C0",
    "gold": "#FFD700",
    "platinum": "#E5E4E2",
}

# Darker versions of frame colors for borders/accents
FRAME_ACCENT_COLORS = {
    "bronze": "#8B5A2B",
    "silver": "#808080",
    "gold": "#B8860B",
    "platinum": "#A9A9A9",
}


class ProfileCardGenerator:
    """Generates PNG profile cards for social sharing."""

    def __init__(self):
        self.width = 400
        self.height = 560

    def _load_fonts(self):
        """Load fonts with fallback to default."""
        try:
            title_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24
            )
            body_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16
            )
            small_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
            )
        except OSError:
            # Fallback to default font
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        return title_font, body_font, small_font

    def _draw_frame(self, draw: ImageDraw.Draw, frame_tier: str):
        """Draw the card frame with appropriate color."""
        frame_color = FRAME_COLORS.get(frame_tier, FRAME_COLORS["bronze"])
        accent_color = FRAME_ACCENT_COLORS.get(frame_tier, FRAME_ACCENT_COLORS["bronze"])

        # Draw outer frame
        draw.rectangle([0, 0, self.width - 1, self.height - 1], fill=frame_color)

        # Draw accent border
        draw.rectangle([2, 2, self.width - 3, self.height - 3], outline=accent_color, width=2)

        # Draw inner card area (white background)
        inner_margin = 12
        draw.rectangle(
            [inner_margin, inner_margin, self.width - inner_margin, self.height - inner_margin],
            fill="white",
            outline=accent_color,
            width=1,
        )

    def _draw_avatar_placeholder(self, draw: ImageDraw.Draw, frame_tier: str):
        """Draw avatar placeholder circle."""
        frame_color = FRAME_COLORS.get(frame_tier, FRAME_COLORS["bronze"])
        avatar_center = (self.width // 2, 140)
        avatar_radius = 55

        # Draw avatar border
        draw.ellipse(
            [
                avatar_center[0] - avatar_radius - 3,
                avatar_center[1] - avatar_radius - 3,
                avatar_center[0] + avatar_radius + 3,
                avatar_center[1] + avatar_radius + 3,
            ],
            fill=frame_color,
        )

        # Draw avatar placeholder
        draw.ellipse(
            [
                avatar_center[0] - avatar_radius,
                avatar_center[1] - avatar_radius,
                avatar_center[0] + avatar_radius,
                avatar_center[1] + avatar_radius,
            ],
            fill="#E8E8E8",
        )

        # Draw placeholder icon (simple user silhouette)
        head_radius = 18
        draw.ellipse(
            [
                avatar_center[0] - head_radius,
                avatar_center[1] - 25 - head_radius,
                avatar_center[0] + head_radius,
                avatar_center[1] - 25 + head_radius,
            ],
            fill="#BDBDBD",
        )
        # Body arc
        draw.arc(
            [
                avatar_center[0] - 35,
                avatar_center[1] - 5,
                avatar_center[0] + 35,
                avatar_center[1] + 45,
            ],
            start=180,
            end=0,
            fill="#BDBDBD",
            width=35,
        )

    def _truncate_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
        """Truncate text with ellipsis if too long."""
        if font.getlength(text) <= max_width:
            return text

        while font.getlength(text + "...") > max_width and len(text) > 0:
            text = text[:-1]
        return text + "..."

    async def generate(
        self,
        display_name: str,
        username: str,
        frame_tier: str,
        tagline: Optional[str] = None,
        card_type: Optional[str] = None,
        cards_for_trade: int = 0,
        signature_card_name: Optional[str] = None,
        member_since: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> bytes:
        """
        Generate a profile card PNG image.

        Args:
            display_name: User's display name
            username: User's username
            frame_tier: Frame tier (bronze, silver, gold, platinum)
            tagline: User's tagline
            card_type: Card type (collector, trader, brewer, investor)
            cards_for_trade: Number of cards available for trade
            signature_card_name: Name of user's signature card
            member_since: Formatted membership date string
            avatar_url: URL to user's avatar (not currently used)

        Returns:
            PNG image as bytes
        """
        frame_color = FRAME_COLORS.get(frame_tier, FRAME_COLORS["bronze"])
        accent_color = FRAME_ACCENT_COLORS.get(frame_tier, FRAME_ACCENT_COLORS["bronze"])

        # Create image
        image = Image.new("RGB", (self.width, self.height), "white")
        draw = ImageDraw.Draw(image)

        # Load fonts
        title_font, body_font, small_font = self._load_fonts()

        # Draw frame
        self._draw_frame(draw, frame_tier)

        # Draw avatar placeholder
        self._draw_avatar_placeholder(draw, frame_tier)

        # Draw display name/username at top
        name_text = display_name or username
        name_text = self._truncate_text(name_text, title_font, self.width - 60)
        draw.text(
            (self.width // 2, 55),
            name_text,
            fill="#1A1A1A",
            font=title_font,
            anchor="mt",
        )

        # Draw card type badge if set
        y_pos = 215
        if card_type:
            badge_text = card_type.upper()
            # Draw badge background
            badge_width = body_font.getlength(badge_text) + 20
            badge_left = (self.width - badge_width) // 2
            draw.rounded_rectangle(
                [badge_left, y_pos - 5, badge_left + badge_width, y_pos + 22],
                radius=5,
                fill=frame_color,
            )
            draw.text(
                (self.width // 2, y_pos),
                badge_text,
                fill="white",
                font=body_font,
                anchor="mt",
            )
            y_pos += 40
        else:
            y_pos += 15

        # Draw tagline if set
        if tagline:
            tagline_display = f'"{tagline}"'
            tagline_display = self._truncate_text(tagline_display, small_font, self.width - 50)
            draw.text(
                (self.width // 2, y_pos),
                tagline_display,
                fill="#666666",
                font=small_font,
                anchor="mt",
            )
            y_pos += 30
        else:
            y_pos += 10

        # Draw divider line
        draw.line(
            [(40, y_pos), (self.width - 40, y_pos)],
            fill="#E0E0E0",
            width=1,
        )
        y_pos += 20

        # Draw stats section
        draw.text(
            (self.width // 2, y_pos),
            "STATS",
            fill=accent_color,
            font=small_font,
            anchor="mt",
        )
        y_pos += 25

        # Cards for trade
        draw.text(
            (self.width // 2, y_pos),
            f"Cards for Trade: {cards_for_trade}",
            fill="#333333",
            font=body_font,
            anchor="mt",
        )
        y_pos += 35

        # Draw signature card if set
        if signature_card_name:
            draw.line(
                [(60, y_pos), (self.width - 60, y_pos)],
                fill="#E0E0E0",
                width=1,
            )
            y_pos += 15

            draw.text(
                (self.width // 2, y_pos),
                "SIGNATURE CARD",
                fill=accent_color,
                font=small_font,
                anchor="mt",
            )
            y_pos += 20

            sig_card_display = self._truncate_text(signature_card_name, body_font, self.width - 50)
            draw.text(
                (self.width // 2, y_pos),
                sig_card_display,
                fill="#333333",
                font=body_font,
                anchor="mt",
            )
            y_pos += 35

        # Draw member since at bottom
        if member_since:
            draw.text(
                (self.width // 2, self.height - 35),
                f"Member since {member_since}",
                fill="#999999",
                font=small_font,
                anchor="mt",
            )

        # Draw platform branding at very bottom
        draw.text(
            (self.width // 2, self.height - 18),
            "Dualcaster Deals",
            fill=accent_color,
            font=small_font,
            anchor="mt",
        )

        # Convert to bytes
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer.getvalue()
