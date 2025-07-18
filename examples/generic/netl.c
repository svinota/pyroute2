/*
 * Generic netlink sample -- kernel module
 * Use `make` to compile and `insmod` to load the module
 *
 * Sergiy Lozovsky <sergiy.lozovsky@gmail.com>
 * Peter Saveliev <peter@svinota.eu>
 *
 * Requires kernel 4.10+
 */
#include <linux/module.h>       /* Needed by all modules */
#include <linux/kernel.h>       /* Needed for KERN_INFO */
#include <linux/init.h>         /* Needed for the macros */
#include <net/genetlink.h>

#define EXMPL_GENL_FAMILY_NAME "ECHO_GENL"
#define EXMPL_GENL_VERSION 0x1

/* attributes (variables): the index in this enum is used as
 *             a reference for the type, userspace application
 *             has to indicate the corresponding type
 */
enum {
    EXMPL_NLA_UNSPEC,
    EXMPL_NLA_STR,
    __EXMPL_NLA_MAX,
};
#define EXMPL_NLA_MAX (__EXMPL_NLA_MAX - 1)

/* ... and the same for commands
 */
enum {
    EXMPL_CMD_UNSPEC,
    EXMPL_CMD_ECHO,
    __EXMPL_CMD_MAX,
};
#define EXMPL_CMD_MAX (__EXMPL_CMD_MAX - 1)


/* attribute policy: defines which attribute has which type (e.g int, char * etc)
 * possible values defined in net/netlink.h
 */
static struct nla_policy exmpl_genl_policy[__EXMPL_NLA_MAX] = {
        [EXMPL_NLA_STR] = { .type = NLA_NUL_STRING },
};

static struct genl_family exmpl_genl_family;

static int exmpl_cmd_echo(struct sk_buff *skb, struct genl_info *info)
{
    struct sk_buff *skb_out;
    void *msg_head;
    const char *msg;

    if (!info->attrs[EXMPL_NLA_STR])
        return -EINVAL;

    msg = nla_data(info->attrs[EXMPL_NLA_STR]);

    pr_info("exmpl_genl: received: %s\n", msg);

    skb_out = genlmsg_new(NLMSG_GOODSIZE, GFP_KERNEL);
    if (!skb_out)
        return -ENOMEM;

    msg_head = genlmsg_put(skb_out, info->snd_portid, info->snd_seq,
                           &exmpl_genl_family, 0, EXMPL_CMD_ECHO);
    if (!msg_head) {
        nlmsg_free(skb_out);
        return -ENOMEM;
    }

    if (nla_put_string(skb_out, EXMPL_NLA_STR, msg)) {
        nlmsg_free(skb_out);
        return -EMSGSIZE;
    }

    genlmsg_end(skb_out, msg_head);
    return genlmsg_reply(skb_out, info);
}

/* commands: mapping between commands and actual functions*/
static const struct genl_ops exmpl_genl_ops_echo[] = {
    {
        .cmd = EXMPL_CMD_ECHO,
        .flags = 0,
        .policy = exmpl_genl_policy,
        .doit = exmpl_cmd_echo,
    },
};

/* family definition */
static struct genl_family exmpl_genl_family __ro_after_init = {
        .name = EXMPL_GENL_FAMILY_NAME,  //the name of this family, used by userspace application
        .version = EXMPL_GENL_VERSION,   //version number
        .maxattr = EXMPL_NLA_MAX,
        .module = THIS_MODULE,
        .ops = exmpl_genl_ops_echo,
        .n_ops = ARRAY_SIZE(exmpl_genl_ops_echo),
};



static int __init exmpl_genl_init(void)
{
        int rc;
        rc = genl_register_family(&exmpl_genl_family);
        if (rc != 0) {
            printk(KERN_INFO "rkmod: genl_register_family failed %d\n", rc);
            return 1;
        }
        printk(KERN_INFO "Generic netlink example loaded, protocol version %d\n", EXMPL_GENL_VERSION);
        return 0;
}

static void __exit exmpl_genl_exit(void)
{
        int ret;
        /*unregister the family*/
        ret = genl_unregister_family(&exmpl_genl_family);
        if(ret !=0){
                printk("unregister family %i\n",ret);
        }
}

module_init(exmpl_genl_init);
module_exit(exmpl_genl_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Simple generic netlink echo module");
