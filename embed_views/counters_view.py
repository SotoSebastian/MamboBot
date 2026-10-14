import discord
from management.vip_users import VIPUsers
from management.word_counter import WordCounter


class CountersView(discord.ui.View):
    def __init__(self, bot, timeout=60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.counterMessage = None
        self.removeCounterMessage = None
        self.removeKeywordMessage = None
        self.selectCounterMessage = None
        self.counters = None

    async def send_page(self, interaction: discord.Interaction, first_response=False):
        embed = discord.Embed(
            title="Contadores de palabras:",
            color=0xa600ff,
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)

        # Obtener la lista de contadores y sus palabras clave
        self.counters = await WordCounter().loadWordCounters()

        if len(self.counters[1]) <= 0:
            embed.description = "No hay contadores de palabras. Añade uno para comenzar."
        else:
            for counter_name, count in self.counters[1].items():
                keywords = [
                    f"- '{keyword}'"
                    for keyword, assigned_counter in self.counters[0].items()
                    if assigned_counter == counter_name
                ]

                embed.add_field(
                    name=f"{counter_name}: {count}",
                    value="\n".join(keywords) if keywords else "No hay palabras clave asignadas.",
                    inline=False
                )

        if first_response:
            self.counterMessage = await interaction.response.send_message(
                embed=embed,
                view=self,
                ephemeral=False
            )
        else:
            await self.counterMessage.resource.edit(embed=embed, view=self)

    @discord.ui.button(
        label="Eliminar contador",
        style=discord.ButtonStyle.danger,
        row=0
    )
    async def remove_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Comprobar si el usuario es administrador
        vipUsers = await VIPUsers().loadVIPUserIDs()

        if interaction.user.id not in vipUsers:
            await interaction.response.send_message(
                "Este comando está reservado para administradores.",
                ephemeral=True
            )
            return

        if len(self.counters[1]) <= 0:
            await interaction.response.send_message(
                "No hay contadores de palabras para eliminar.",
                ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label=counter, value=counter)
            for counter in self.counters[1].keys()
        ]

        class RemoveCounterDropdown(discord.ui.Select):
            def __init__(self, parent_view):
                self.parent_view = parent_view
                super().__init__(
                    placeholder="Selecciona un contador para eliminar...",
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):
                counter_name = self.values[0]

                # Eliminar el contador seleccionado
                await WordCounter().removeCounter(counter_name)

                await select_interaction.response.send_message(
                    f"Se eliminó el contador: {counter_name}",
                    ephemeral=True
                )

                await self.parent_view.send_page(interaction)
                await self.parent_view.removeCounterMessage.resource.delete()

        view = discord.ui.View()
        view.add_item(RemoveCounterDropdown(self))

        self.removeCounterMessage = await interaction.response.send_message(
            "Selecciona el contador que deseas eliminar:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="Eliminar palabra clave",
        style=discord.ButtonStyle.danger,
        row=0
    )
    async def remove_keyword(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Comprobar si el usuario es administrador
        vipUsers = await VIPUsers().loadVIPUserIDs()

        if interaction.user.id not in vipUsers:
            await interaction.response.send_message(
                "Este comando está reservado para administradores.",
                ephemeral=True
            )
            return

        if len(self.counters[1]) <= 0:
            await interaction.response.send_message(
                "No hay contadores de palabras de los que eliminar palabras clave.",
                ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label=counter, value=counter)
            for counter in self.counters[1].keys()
        ]

        class SelectCounterDropdown(discord.ui.Select):
            def __init__(self, parent_view):
                self.parent_view = parent_view
                super().__init__(
                    placeholder="Selecciona un contador...",
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):
                counter_name = self.values[0]

                # Obtener las palabras clave asignadas al contador
                data = await WordCounter().loadWordCounters()
                keywords = [
                    keyword
                    for keyword, assigned_counter in data[0].items()
                    if assigned_counter == counter_name
                ]

                if not keywords:
                    await select_interaction.response.send_message(
                        f"No se encontraron palabras clave para el contador `{counter_name}`.",
                        ephemeral=True
                    )
                    return

                keyword_options = [
                    discord.SelectOption(label=keyword, value=keyword)
                    for keyword in keywords
                ]

                class RemoveKeywordDropdown(discord.ui.Select):
                    def __init__(self, parent_view):
                        self.parent_view = parent_view
                        super().__init__(
                            placeholder="Selecciona una palabra clave para eliminar...",
                            options=keyword_options
                        )

                    async def callback(self, keyword_interaction: discord.Interaction):
                        keyword_to_remove = self.values[0]

                        await WordCounter().removeKeyword(keyword_to_remove)

                        await keyword_interaction.response.send_message(
                            f"Se eliminó la palabra clave `{keyword_to_remove}` "
                            f"del contador `{counter_name}`.",
                            ephemeral=True
                        )

                        await self.parent_view.send_page(interaction)
                        await self.parent_view.selectCounterMessage.resource.delete()
                        await self.parent_view.removeKeywordMessage.resource.delete()

                # Mostrar el selector de palabras clave
                keyword_view = discord.ui.View()
                keyword_view.add_item(RemoveKeywordDropdown(self.parent_view))

                self.parent_view.removeKeywordMessage = await select_interaction.response.send_message(
                    f"Selecciona la palabra clave que deseas eliminar del contador `{counter_name}`:",
                    view=keyword_view,
                    ephemeral=True
                )

        view = discord.ui.View()
        view.add_item(SelectCounterDropdown(self))

        self.selectCounterMessage = await interaction.response.send_message(
            "Selecciona el contador del que deseas eliminar una palabra clave:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="Añadir palabra clave",
        style=discord.ButtonStyle.primary,
        row=0
    )
    async def add_keyword(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Comprobar si el usuario es administrador
        vipUsers = await VIPUsers().loadVIPUserIDs()

        if interaction.user.id not in vipUsers:
            await interaction.response.send_message(
                "Este comando está reservado para administradores.",
                ephemeral=True
            )
            return

        class KeywordModal(discord.ui.Modal, title="Añadir palabra clave y contador"):
            def __init__(self, parent_view):
                super().__init__()
                self.parent_view = parent_view

                self.keyword_input = discord.ui.TextInput(
                    label="Palabra clave",
                    style=discord.TextStyle.short,
                    required=True
                )

                self.counter_input = discord.ui.TextInput(
                    label="Nombre del contador",
                    style=discord.TextStyle.short,
                    required=True
                )

                self.add_item(self.keyword_input)
                self.add_item(self.counter_input)

            async def on_submit(self, interaction: discord.Interaction):
                keyword = self.keyword_input.value.strip()
                counter = self.counter_input.value.strip()

                if not keyword or not counter:
                    await interaction.response.send_message(
                        "La palabra clave y el nombre del contador no pueden estar vacíos.",
                        ephemeral=True
                    )
                    return

                await WordCounter().addKeyword(keyword, counter)

                await interaction.response.send_message(
                    f"Se añadió la palabra clave `{keyword}` al contador `{counter}`.",
                    ephemeral=True
                )

                await self.parent_view.send_page(interaction)

        await interaction.response.send_modal(KeywordModal(self))