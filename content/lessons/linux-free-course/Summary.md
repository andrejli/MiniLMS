# **Lecture 2: Processes and Tasks in Linux**

---

## **Introduction: The Evolution of Computing**
*From Exclusivity to Open-Source Revolution*

Do not fear—we won’t drag you through the entire history of computing, from **Charles Babbage’s Analytical Engine** to **Alan Turing’s Colossus** and the **IBM PC**. What matters is understanding that computers were once **prohibitively expensive** and **inaccessible** technology. Only a tiny elite of scientists and engineers had access to them, let alone the knowledge to operate them.

The rise of **8-bit home computers**—like the **Sinclair ZX Spectrum, Commodore 64, and Atari**—democratized computing, bringing it into households. Yet even these "modern" machines ran **primitive operating systems** incapable of multitasking or supporting multiple users. Systems like **SCO UNIX** and **Solaris** were **astronomically expensive**, far beyond the reach of the average user.

Then came **the penguin**—**Linux**.
Its code was **free, open, and accessible** to anyone with passion. It offered **unprecedented capabilities** for its time and **conquered the world of computing**—well, not the world of *end-users* or those who see computers as a "necessary evil," but it **won the hearts of hackers, sysadmins, developers, and hobbyists**.

Today, **a massive portion of global IT infrastructure runs on Linux**. If you want to **unlock its magic** and lay the **foundation of your knowledge**, read on...

---

---

## **The Linux Terminal: Your Gateway to Power**

When you boot a Linux machine, it follows a **startup sequence**:
1. The system **checks all available hardware and software**.
2. It loads the **Linux kernel** and **resident programs/drivers**.
3. Upon successful boot, it either:
   - Launches a **graphical interface (GUI)**, or
   - Stays in **text mode (terminal)** and prompts for:
     - **Username** (`USERNAME`)
     - **Password** (`PASSWORD`)

---

### **Raspberry Pi Default Credentials**
If you’re using a **Raspberry Pi** with default settings:
- **Username:** `pi`
- **Password:** `raspberry`

After entering the correct credentials, the terminal will display a **command prompt**, such as:
```bash
pi@raspberrypi:~ \$
```

---
### **🐧 Keeping Your Penguin Clean: System Updates**
> *"A well-maintained Linux is a **secure** Linux."*

Before diving into work, **always update your system** at least once every few days. This ensures:

✅ **Latest software versions** (`UPDATE`)
✅ **Critical security patches** (`PATCH`)
✅ **Protection against known vulnerabilities** *(a hacker’s worst nightmare)*

---

#### **🔧 How to Update?**
Linux uses a **package manager** to handle software installations.
For **Raspberry Pi (Debian-based)**, run:

```bash
sudo apt-get update
```

---
#### **⚠️ WARNING**
If the command fails, you may need:
- **Administrative privileges** → Use `sudo` to temporarily escalate permissions.
- **Root access** → Log in as `root` if necessary.

---
🎉 **Congratulations!**
Your system is now ready for action.
The black-and-white terminal may look intimidating—even terrifying—but this is where true control lies.

---
#### **🎨 Craving Colors?**
If you miss the vibrant windows of graphical interfaces like **MATE, GNOME, KDE, or LXDE** (similar to Windows or macOS), run:
```bash
startx
```

But when you’re done admiring the eye candy, return to the command line—because 💻 real hackers live in the terminal.